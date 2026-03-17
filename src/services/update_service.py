"""Automated client update service.

Generates and sends progress update emails to clients.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from ..models.client import Client, ClientStatus
from ..models.project import ProjectStatus
from .client_service import list_clients
from .project_service import get_project_with_sessions, list_projects
from .email_service import send_template

logger = logging.getLogger(__name__)


@dataclass
class ProjectUpdate:
    """Summary of work on a single project."""
    name: str
    hours: float
    tasks: list[str]
    prs: list[str]
    notes: list[str]


@dataclass
class ClientUpdate:
    """Summary of all work for a client in a period."""
    client_name: str
    client_email: str
    period_start: date
    period_end: date
    total_hours: float
    projects: list[ProjectUpdate]
    
    @property
    def has_activity(self) -> bool:
        """Check if there was any activity in this period."""
        return self.total_hours > 0 or any(p.tasks or p.prs for p in self.projects)


def get_client_update(
    client: Client,
    start_date: date,
    end_date: date
) -> ClientUpdate:
    """Generate update summary for a client.
    
    Args:
        client: The client to summarize
        start_date: Start of period (inclusive)
        end_date: End of period (inclusive)
    
    Returns:
        ClientUpdate with work summary
    """
    import json
    
    projects, _ = list_projects(client_id=client.id)
    
    total_hours = 0.0
    project_updates = []
    
    for project in projects:
        result = get_project_with_sessions(project.id)
        if not result:
            continue
        
        proj, sessions = result
        
        project_hours = 0.0
        project_tasks = []
        project_prs = []
        project_notes = []
        
        for session in sessions:
            # Filter to date range
            if session.session_date and start_date <= session.session_date <= end_date:
                if session.hours:
                    project_hours += float(session.hours)
                
                if session.tasks_completed:
                    try:
                        tasks = json.loads(session.tasks_completed)
                        project_tasks.extend(tasks)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                if session.prs_opened:
                    try:
                        prs = json.loads(session.prs_opened)
                        project_prs.extend(prs)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                if session.notes:
                    project_notes.append(session.notes)
        
        if project_hours > 0 or project_tasks or project_prs:
            total_hours += project_hours
            project_updates.append(ProjectUpdate(
                name=proj.name,
                hours=project_hours,
                tasks=project_tasks,
                prs=project_prs,
                notes=project_notes
            ))
    
    return ClientUpdate(
        client_name=client.name or "there",
        client_email=client.email,
        period_start=start_date,
        period_end=end_date,
        total_hours=total_hours,
        projects=project_updates
    )


def format_update_text(update: ClientUpdate) -> str:
    """Format update as plain text for email body.
    
    Args:
        update: The client update to format
    
    Returns:
        Formatted text string
    """
    lines = []
    
    period = f"{update.period_start.strftime('%b %d')} - {update.period_end.strftime('%b %d, %Y')}"
    lines.append(f"Work Summary: {period}")
    lines.append("=" * 40)
    lines.append("")
    
    if not update.has_activity:
        lines.append("No work sessions logged this period.")
        lines.append("")
        lines.append("Questions? Just reply to this email.")
        return "\n".join(lines)
    
    lines.append(f"Total Hours: {update.total_hours:.1f}")
    lines.append("")
    
    for project in update.projects:
        lines.append(f"## {project.name}")
        lines.append(f"   Hours: {project.hours:.1f}")
        
        if project.tasks:
            lines.append("   Completed:")
            for task in project.tasks:
                lines.append(f"   - {task}")
        
        if project.prs:
            lines.append("   Pull Requests:")
            for pr in project.prs:
                lines.append(f"   - {pr}")
        
        if project.notes:
            lines.append("   Notes:")
            for note in project.notes:
                lines.append(f"   > {note}")
        
        lines.append("")
    
    lines.append("---")
    lines.append("View full details in your portal: https://blackabee.com/hire/portal/")
    lines.append("")
    lines.append("Questions? Just reply to this email.")
    
    return "\n".join(lines)


def send_client_update(
    client: Client,
    start_date: date,
    end_date: date,
    subject_prefix: str = "Weekly Update"
) -> bool:
    """Generate and send update email to a client.
    
    Args:
        client: The client to update
        start_date: Start of period
        end_date: End of period
        subject_prefix: Prefix for email subject
    
    Returns:
        True if email sent successfully
    """
    update = get_client_update(client, start_date, end_date)
    
    if not update.has_activity:
        logger.info(f"No activity for {client.email} in period, skipping")
        return True  # Not an error, just nothing to report
    
    body = format_update_text(update)
    period = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}"
    subject = f"{subject_prefix}: {period}"
    
    from .email_service import send_email
    
    success = send_email(
        to=client.email,
        subject=subject,
        body=body
    )
    
    if success:
        logger.info(f"Sent update to {client.email}")
    else:
        logger.error(f"Failed to send update to {client.email}")
    
    return success


def send_weekly_updates() -> tuple[int, int]:
    """Send weekly updates to all active clients.
    
    Returns:
        Tuple of (sent_count, failed_count)
    """
    today = date.today()
    # Last 7 days
    start_date = today - timedelta(days=7)
    end_date = today - timedelta(days=1)
    
    clients, _ = list_clients(status=ClientStatus.ACTIVE)
    
    sent = 0
    failed = 0
    
    for client in clients:
        if send_client_update(client, start_date, end_date, "Weekly Update"):
            sent += 1
        else:
            failed += 1
    
    logger.info(f"Weekly updates: {sent} sent, {failed} failed")
    return sent, failed


def send_monthly_updates() -> tuple[int, int]:
    """Send monthly updates to all active clients.
    
    Returns:
        Tuple of (sent_count, failed_count)
    """
    today = date.today()
    # Last month (1st to last day)
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    clients, _ = list_clients(status=ClientStatus.ACTIVE)
    
    sent = 0
    failed = 0
    
    for client in clients:
        if send_client_update(client, last_month_start, last_month_end, "Monthly Summary"):
            sent += 1
        else:
            failed += 1
    
    logger.info(f"Monthly updates: {sent} sent, {failed} failed")
    return sent, failed
