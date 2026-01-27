"""Admin dashboard API routes."""

import logging
import secrets
import time
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..config import get_config
from ..models.client import Client, ClientStatus
from ..models.project import Project, ProjectStatus
from ..services import (
    approve_project,
    get_client_by_id,
    get_project,
    get_project_with_sessions,
    list_clients,
    list_projects,
    log_session,
    parse_session_json,
    reject_project,
)
from ..utils.db import get_session as get_db_session

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple in-memory session store (acceptable for single-instance MVP)
_sessions: dict[str, bool] = {}

# Rate limiting for login attempts
# Key: IP address, Value: (attempt_count, first_attempt_timestamp)
_login_attempts: dict[str, tuple[int, float]] = {}

# Rate limit settings
RATE_LIMIT_MAX_ATTEMPTS = 5  # Max failed attempts
RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minute window
RATE_LIMIT_LOCKOUT_SECONDS = 900  # 15 minute lockout after max attempts


def _check_rate_limit(ip: str) -> None:
    """Check if IP is rate limited for login attempts.
    
    Raises HTTPException 429 if too many attempts.
    """
    now = time.time()
    
    if ip in _login_attempts:
        attempts, first_attempt = _login_attempts[ip]
        
        # Check if we're in lockout period (exceeded max attempts)
        if attempts >= RATE_LIMIT_MAX_ATTEMPTS:
            lockout_remaining = (first_attempt + RATE_LIMIT_LOCKOUT_SECONDS) - now
            if lockout_remaining > 0:
                logger.warning(f"Rate limited login attempt from {ip}, {int(lockout_remaining)}s remaining")
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many login attempts. Try again in {int(lockout_remaining)} seconds."
                )
            else:
                # Lockout expired, reset
                del _login_attempts[ip]
        
        # Check if window has expired
        elif now - first_attempt > RATE_LIMIT_WINDOW_SECONDS:
            # Window expired, reset
            del _login_attempts[ip]


def _record_failed_attempt(ip: str) -> None:
    """Record a failed login attempt."""
    now = time.time()
    
    if ip in _login_attempts:
        attempts, first_attempt = _login_attempts[ip]
        _login_attempts[ip] = (attempts + 1, first_attempt)
    else:
        _login_attempts[ip] = (1, now)
    
    attempts = _login_attempts[ip][0]
    remaining = RATE_LIMIT_MAX_ATTEMPTS - attempts
    
    if remaining > 0:
        logger.warning(f"Failed login attempt from {ip} ({attempts}/{RATE_LIMIT_MAX_ATTEMPTS})")
    else:
        logger.warning(f"Max login attempts reached from {ip}, locked out for {RATE_LIMIT_LOCKOUT_SECONDS}s")


def _clear_rate_limit(ip: str) -> None:
    """Clear rate limit on successful login."""
    if ip in _login_attempts:
        del _login_attempts[ip]


class LoginRequest(BaseModel):
    """Admin login request."""
    password: str


class SessionLogRequest(BaseModel):
    """Work session log request."""
    project_id: int
    session_date: str  # ISO format YYYY-MM-DD
    hours: float
    tasks_completed: list[str] = []
    prs_opened: list[str] = []
    notes: Optional[str] = None


class RejectRequest(BaseModel):
    """Project rejection request."""
    reason: str


def verify_session(session_id: Optional[str] = Cookie(None, alias="admin_session")):
    """Verify admin session cookie.
    
    Raises HTTPException 401 if not authenticated.
    """
    if not session_id or session_id not in _sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id


def _client_to_dict(client: Client) -> dict:
    """Convert Client to dict for JSON response."""
    return {
        "id": client.id,
        "email": client.email,
        "name": client.name,
        "status": client.status.value,
        "stripe_customer_id": client.stripe_customer_id,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None
    }


def _project_to_dict(project: Project) -> dict:
    """Convert Project to dict for JSON response."""
    return {
        "id": project.id,
        "client_id": project.client_id,
        "name": project.name,
        "repo_url": project.repo_url,
        "description": project.description,
        "tech_stack": project.tech_stack,
        "access_method": project.access_method,
        "coding_standards": project.coding_standards,
        "do_not_touch": project.do_not_touch,
        "communication_preference": project.communication_preference,
        "status": project.status.value,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None
    }


@router.post("/api/admin/login")
async def login(data: LoginRequest, request: Request, response: Response):
    """Admin login.
    
    Sets session cookie on success.
    Rate limited: 5 attempts per 5 minutes, then 15 minute lockout.
    """
    # Get client IP (handle proxy headers)
    ip = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.client.host
    
    # Check rate limit before processing
    _check_rate_limit(ip)
    
    config = get_config()
    
    if not config.admin.password:
        logger.error("Admin password not configured")
        raise HTTPException(status_code=500, detail="Admin not configured")
    
    if data.password != config.admin.password:
        _record_failed_attempt(ip)
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Successful login - clear any rate limit
    _clear_rate_limit(ip)
    
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = True
    
    response.set_cookie(
        key="admin_session",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400  # 24 hours
    )
    
    logger.info(f"Admin logged in from {ip}")
    return {"success": True}


@router.post("/api/admin/logout")
async def logout(response: Response, session_id: str = Depends(verify_session)):
    """Admin logout.
    
    Clears session cookie.
    """
    if session_id in _sessions:
        del _sessions[session_id]
    
    response.delete_cookie("admin_session")
    return {"success": True}


@router.get("/api/admin/clients")
async def list_clients_endpoint(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    _: str = Depends(verify_session)
):
    """List all clients with pagination."""
    status_enum = ClientStatus(status) if status else None
    clients, total = list_clients(status=status_enum, page=page, limit=limit)
    
    return {
        "clients": [_client_to_dict(c) for c in clients],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/api/admin/clients/{client_id}")
async def get_client_endpoint(
    client_id: int,
    _: str = Depends(verify_session)
):
    """Get a single client with their projects."""
    client = get_client_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    projects, _ = list_projects(client_id=client_id)
    
    return {
        "client": _client_to_dict(client),
        "projects": [_project_to_dict(p) for p in projects]
    }


@router.get("/api/admin/projects")
async def list_projects_endpoint(
    status: Optional[str] = None,
    client_id: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
    _: str = Depends(verify_session)
):
    """List all projects with pagination."""
    status_enum = ProjectStatus(status) if status else None
    projects, total = list_projects(
        status=status_enum,
        client_id=client_id,
        page=page,
        limit=limit
    )
    
    return {
        "projects": [_project_to_dict(p) for p in projects],
        "total": total,
        "page": page,
        "limit": limit
    }


@router.get("/api/admin/projects/{project_id}")
async def get_project_endpoint(
    project_id: int,
    _: str = Depends(verify_session)
):
    """Get a single project with work sessions."""
    result = get_project_with_sessions(project_id)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project, sessions = result
    
    return {
        "project": _project_to_dict(project),
        "sessions": [parse_session_json(s) for s in sessions]
    }


@router.post("/api/admin/projects/{project_id}/approve")
async def approve_project_endpoint(
    project_id: int,
    _: str = Depends(verify_session)
):
    """Approve a project after guardrail review."""
    try:
        project = approve_project(project_id)
        logger.info(f"Approved project {project_id}")
        return {"project": _project_to_dict(project)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/admin/projects/{project_id}/reject")
async def reject_project_endpoint(
    project_id: int,
    data: RejectRequest,
    _: str = Depends(verify_session)
):
    """Reject a project with a reason."""
    try:
        project = reject_project(project_id, data.reason)
        logger.info(f"Rejected project {project_id}: {data.reason}")
        return {"project": _project_to_dict(project)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/admin/sessions")
async def log_session_endpoint(
    data: SessionLogRequest,
    _: str = Depends(verify_session)
):
    """Log a work session."""
    try:
        session_date = date.fromisoformat(data.session_date)
        session = log_session(
            project_id=data.project_id,
            session_date=session_date,
            hours=Decimal(str(data.hours)),
            tasks_completed=data.tasks_completed,
            prs_opened=data.prs_opened,
            notes=data.notes
        )
        logger.info(f"Logged session for project {data.project_id}: {data.hours}h")
        return {"session": parse_session_json(session)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/admin/communications")
async def list_communications_endpoint(
    client_id: Optional[int] = None,
    direction: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    _: str = Depends(verify_session)
):
    """List communications with pagination."""
    from ..models.communication import Communication, CommunicationDirection
    
    with get_db_session() as session:
        query = session.query(Communication)
        
        if client_id is not None:
            query = query.filter_by(client_id=client_id)
        if direction is not None:
            query = query.filter_by(direction=CommunicationDirection(direction))
        
        total = query.count()
        
        communications = (
            query
            .order_by(Communication.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        
        result = []
        for comm in communications:
            result.append({
                "id": comm.id,
                "client_id": comm.client_id,
                "direction": comm.direction.value,
                "subject": comm.subject,
                "content": comm.content,
                "message_id": comm.message_id,
                "created_at": comm.created_at.isoformat() if comm.created_at else None
            })
        
        return {
            "communications": result,
            "total": total,
            "page": page,
            "limit": limit
        }


@router.get("/api/admin/stats")
async def get_stats(_: str = Depends(verify_session)):
    """Get dashboard statistics."""
    active_clients, _ = list_clients(status=ClientStatus.ACTIVE)
    all_clients, total_clients = list_clients()
    all_projects, total_projects = list_projects()
    active_projects, _ = list_projects(status=ProjectStatus.ACTIVE)
    intake_projects, _ = list_projects(status=ProjectStatus.INTAKE)
    
    return {
        "clients": {
            "total": total_clients,
            "active": len(active_clients)
        },
        "projects": {
            "total": total_projects,
            "active": len(active_projects),
            "pending_review": len(intake_projects)
        }
    }
