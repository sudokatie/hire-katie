"""Client portal routes.

Allows clients to view their work sessions, hours, and PRs.
Authentication via email magic link token.
"""

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from ..config import get_config
from ..models.client import Client, ClientStatus
from ..models.project import ProjectStatus
from ..services import (
    get_client_by_email,
    get_client_by_id,
    get_project_with_sessions,
    list_projects,
    parse_session_json,
    send_template,
)
from ..utils.db import get_session as get_db_session

router = APIRouter()
logger = logging.getLogger(__name__)


# Token store: token -> (client_id, expiry_timestamp)
_portal_tokens: dict[str, tuple[int, float]] = {}

# Session store: session_id -> client_id
_portal_sessions: dict[str, int] = {}

# Magic link store: token -> (email, expiry_timestamp)
_magic_links: dict[str, tuple[str, float]] = {}

# Token settings
MAGIC_LINK_EXPIRY_SECONDS = 900  # 15 minutes
SESSION_EXPIRY_SECONDS = 86400 * 7  # 7 days


class MagicLinkRequest(BaseModel):
    """Request for magic link login."""
    email: EmailStr


class TokenLoginRequest(BaseModel):
    """Login with magic link token."""
    token: str


def _generate_magic_link_token() -> str:
    """Generate a secure magic link token."""
    return secrets.token_urlsafe(48)


def _generate_session_id() -> str:
    """Generate a session ID."""
    return secrets.token_urlsafe(32)


def create_magic_link(email: str) -> str:
    """Create a magic link token for the given email.
    
    Returns the token (caller should email it to user).
    """
    # Clean up expired tokens first
    now = time.time()
    expired = [k for k, v in _magic_links.items() if v[1] < now]
    for k in expired:
        del _magic_links[k]
    
    token = _generate_magic_link_token()
    expiry = now + MAGIC_LINK_EXPIRY_SECONDS
    _magic_links[token] = (email.lower(), expiry)
    
    logger.info(f"Created magic link for {email}")
    return token


def verify_magic_link(token: str) -> Optional[str]:
    """Verify a magic link token.
    
    Returns the email if valid, None if invalid or expired.
    Consumes the token (one-time use).
    """
    if token not in _magic_links:
        return None
    
    email, expiry = _magic_links[token]
    del _magic_links[token]  # One-time use
    
    if time.time() > expiry:
        logger.warning(f"Expired magic link used for {email}")
        return None
    
    return email


def create_portal_session(client_id: int) -> str:
    """Create a portal session for a client.
    
    Returns the session ID.
    """
    session_id = _generate_session_id()
    _portal_sessions[session_id] = client_id
    
    logger.info(f"Created portal session for client {client_id}")
    return session_id


def verify_portal_session(
    session_id: Optional[str] = Cookie(None, alias="portal_session")
) -> int:
    """Verify portal session cookie.
    
    Returns client_id if valid.
    Raises HTTPException 401 if not authenticated.
    """
    if not session_id or session_id not in _portal_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _portal_sessions[session_id]


def _client_summary(client: Client) -> dict:
    """Convert Client to summary dict for portal."""
    return {
        "id": client.id,
        "email": client.email,
        "name": client.name,
        "status": client.status.value,
        "member_since": client.created_at.isoformat() if client.created_at else None
    }


def _project_summary(project) -> dict:
    """Convert Project to summary dict for portal."""
    return {
        "id": project.id,
        "name": project.name,
        "repo_url": project.repo_url,
        "status": project.status.value,
        "created_at": project.created_at.isoformat() if project.created_at else None
    }


def _session_summary(session) -> dict:
    """Convert WorkSession to summary dict for portal."""
    import json
    
    tasks = []
    prs = []
    
    if session.tasks_completed:
        try:
            tasks = json.loads(session.tasks_completed)
        except (json.JSONDecodeError, TypeError):
            tasks = []
    
    if session.prs_opened:
        try:
            prs = json.loads(session.prs_opened)
        except (json.JSONDecodeError, TypeError):
            prs = []
    
    return {
        "id": session.id,
        "date": session.session_date.isoformat() if session.session_date else None,
        "hours": float(session.hours) if session.hours else 0,
        "tasks_completed": tasks,
        "prs_opened": prs,
        "notes": session.notes
    }


@router.post("/api/portal/request-login")
async def request_login(data: MagicLinkRequest):
    """Request a magic link for portal login.
    
    Sends an email with a login link if the client exists.
    Always returns success to prevent email enumeration.
    """
    email = data.email.lower()
    
    # Check if client exists
    client = get_client_by_email(email)
    
    if client and client.status in (ClientStatus.ACTIVE, ClientStatus.PAUSED):
        token = create_magic_link(email)
        
        # Build magic link URL
        config = get_config()
        base_url = f"http://{config.server.host}:{config.server.port}"
        if config.server.host == "0.0.0.0":
            base_url = f"http://localhost:{config.server.port}"
        magic_link = f"{base_url}/portal/login?token={token}"
        
        # Send email with magic link
        client_name = client.name or "there"
        email_sent = send_template(
            to=email,
            template_name="portal_login",
            variables={
                "name": client_name,
                "magic_link": magic_link
            }
        )
        
        if email_sent:
            logger.info(f"Magic link email sent to {email}")
        else:
            # Log the link as fallback (also useful for development)
            logger.warning(f"Failed to send magic link email to {email}")
            logger.info(f"Magic link for {email}: {magic_link}")
    else:
        logger.info(f"Login request for unknown/inactive email: {email}")
    
    # Always return success to prevent enumeration
    return {
        "success": True,
        "message": "If an account exists, a login link has been sent."
    }


@router.post("/api/portal/login")
async def login_with_token(data: TokenLoginRequest, response: Response):
    """Login with magic link token.
    
    Sets session cookie on success.
    """
    email = verify_magic_link(data.token)
    
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    client = get_client_by_email(email)
    
    if not client:
        raise HTTPException(status_code=401, detail="Client not found")
    
    if client.status not in (ClientStatus.ACTIVE, ClientStatus.PAUSED):
        raise HTTPException(status_code=403, detail="Account not active")
    
    session_id = create_portal_session(client.id)
    
    response.set_cookie(
        key="portal_session",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=SESSION_EXPIRY_SECONDS
    )
    
    logger.info(f"Portal login successful for {email}")
    return {"success": True, "client": _client_summary(client)}


@router.post("/api/portal/logout")
async def logout(response: Response, client_id: int = Depends(verify_portal_session)):
    """Logout from portal."""
    # Find and remove session
    to_remove = [k for k, v in _portal_sessions.items() if v == client_id]
    for k in to_remove:
        del _portal_sessions[k]
    
    response.delete_cookie("portal_session")
    return {"success": True}


@router.get("/api/portal/me")
async def get_current_client(client_id: int = Depends(verify_portal_session)):
    """Get current authenticated client info."""
    client = get_client_by_id(client_id)
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return {"client": _client_summary(client)}


@router.get("/api/portal/projects")
async def list_client_projects(client_id: int = Depends(verify_portal_session)):
    """List all projects for the authenticated client."""
    projects, total = list_projects(client_id=client_id)
    
    return {
        "projects": [_project_summary(p) for p in projects],
        "total": total
    }


@router.get("/api/portal/projects/{project_id}")
async def get_project_detail(
    project_id: int,
    client_id: int = Depends(verify_portal_session)
):
    """Get project detail with work sessions.
    
    Only accessible if the project belongs to the authenticated client.
    """
    result = get_project_with_sessions(project_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project, sessions = result
    
    # Verify ownership
    if project.client_id != client_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Calculate totals
    total_hours = sum(float(s.hours) for s in sessions if s.hours)
    total_prs = 0
    total_tasks = 0
    
    for s in sessions:
        summary = _session_summary(s)
        total_prs += len(summary["prs_opened"])
        total_tasks += len(summary["tasks_completed"])
    
    return {
        "project": _project_summary(project),
        "sessions": [_session_summary(s) for s in sessions],
        "totals": {
            "hours": total_hours,
            "prs": total_prs,
            "tasks": total_tasks
        }
    }


@router.get("/api/portal/summary")
async def get_client_summary(client_id: int = Depends(verify_portal_session)):
    """Get summary of all work for the authenticated client.
    
    Includes total hours, PRs, and tasks across all projects.
    """
    projects, _ = list_projects(client_id=client_id)
    
    total_hours = 0.0
    total_prs = 0
    total_tasks = 0
    project_summaries = []
    
    for project in projects:
        result = get_project_with_sessions(project.id)
        if result:
            _, sessions = result
            project_hours = sum(float(s.hours) for s in sessions if s.hours)
            project_prs = 0
            project_tasks = 0
            
            for s in sessions:
                summary = _session_summary(s)
                project_prs += len(summary["prs_opened"])
                project_tasks += len(summary["tasks_completed"])
            
            total_hours += project_hours
            total_prs += project_prs
            total_tasks += project_tasks
            
            project_summaries.append({
                "id": project.id,
                "name": project.name,
                "status": project.status.value,
                "hours": project_hours,
                "prs": project_prs,
                "tasks": project_tasks
            })
    
    return {
        "projects": project_summaries,
        "totals": {
            "hours": total_hours,
            "prs": total_prs,
            "tasks": total_tasks,
            "projects": len(projects)
        }
    }


@router.get("/api/portal/reports/sessions")
async def download_sessions_report(
    client_id: int = Depends(verify_portal_session),
    format: str = "csv"
):
    """Download work sessions report as CSV or JSON.
    
    Includes all sessions across all projects.
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    if format not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")
    
    projects, _ = list_projects(client_id=client_id)
    
    all_sessions = []
    for project in projects:
        result = get_project_with_sessions(project.id)
        if result:
            proj, sessions = result
            for s in sessions:
                summary = _session_summary(s)
                all_sessions.append({
                    "project": proj.name,
                    "date": summary["date"],
                    "hours": summary["hours"],
                    "tasks": "; ".join(summary["tasks_completed"]),
                    "prs": "; ".join(summary["prs_opened"]),
                    "notes": summary["notes"] or ""
                })
    
    # Sort by date descending
    all_sessions.sort(key=lambda x: x["date"] or "", reverse=True)
    
    if format == "json":
        return {"sessions": all_sessions}
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["project", "date", "hours", "tasks", "prs", "notes"])
    writer.writeheader()
    writer.writerows(all_sessions)
    
    csv_content = output.getvalue()
    output.close()
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=work_sessions.csv"}
    )


@router.get("/api/portal/reports/summary")
async def download_summary_report(
    client_id: int = Depends(verify_portal_session),
    format: str = "csv"
):
    """Download monthly summary report as CSV or JSON.
    
    Groups hours by month for billing reconciliation.
    """
    import csv
    import io
    from collections import defaultdict
    from fastapi.responses import StreamingResponse
    
    if format not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")
    
    projects, _ = list_projects(client_id=client_id)
    
    # Group by month
    monthly_data = defaultdict(lambda: {"hours": 0.0, "tasks": 0, "prs": 0})
    
    for project in projects:
        result = get_project_with_sessions(project.id)
        if result:
            _, sessions = result
            for s in sessions:
                summary = _session_summary(s)
                if summary["date"]:
                    # Extract YYYY-MM from date
                    month = summary["date"][:7]
                    monthly_data[month]["hours"] += summary["hours"]
                    monthly_data[month]["tasks"] += len(summary["tasks_completed"])
                    monthly_data[month]["prs"] += len(summary["prs_opened"])
    
    # Convert to sorted list
    monthly_list = [
        {"month": month, **data}
        for month, data in sorted(monthly_data.items(), reverse=True)
    ]
    
    if format == "json":
        return {"monthly_summary": monthly_list}
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["month", "hours", "tasks", "prs"])
    writer.writeheader()
    writer.writerows(monthly_list)
    
    csv_content = output.getvalue()
    output.close()
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=monthly_summary.csv"}
    )
