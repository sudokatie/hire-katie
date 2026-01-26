"""Work session logging service."""

import json
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import extract, func

from ..models.project import Project
from ..models.work_session import WorkSession
from ..utils.db import get_session


def log_session(
    project_id: int,
    session_date: date,
    hours: Decimal,
    tasks_completed: Optional[list[str]] = None,
    prs_opened: Optional[list[str]] = None,
    notes: Optional[str] = None
) -> WorkSession:
    """Log a work session for a project.
    
    Args:
        project_id: Project ID
        session_date: Date of the session
        hours: Hours worked
        tasks_completed: List of completed tasks
        prs_opened: List of PR URLs
        notes: Session notes
    
    Returns:
        The created work session
    
    Raises:
        ValueError: If project not found
    """
    with get_session() as db:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        session = WorkSession(
            project_id=project_id,
            session_date=session_date,
            hours=hours,
            tasks_completed=json.dumps(tasks_completed or []),
            prs_opened=json.dumps(prs_opened or []),
            notes=notes
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        db.expunge(session)
        return session


def get_sessions_for_project(project_id: int) -> list[WorkSession]:
    """Get all work sessions for a project.
    
    Args:
        project_id: Project ID
    
    Returns:
        List of work sessions ordered by date descending
    """
    with get_session() as db:
        sessions = (
            db.query(WorkSession)
            .filter_by(project_id=project_id)
            .order_by(WorkSession.session_date.desc())
            .all()
        )
        
        for session in sessions:
            db.expunge(session)
        
        return sessions


def get_total_hours(project_id: int) -> Decimal:
    """Get total hours worked on a project.
    
    Args:
        project_id: Project ID
    
    Returns:
        Total hours as Decimal
    """
    with get_session() as db:
        result = (
            db.query(func.sum(WorkSession.hours))
            .filter_by(project_id=project_id)
            .scalar()
        )
        return result or Decimal(0)


def get_monthly_summary(project_id: int, year: int, month: int) -> dict:
    """Get a summary of work for a specific month.
    
    Args:
        project_id: Project ID
        year: Year
        month: Month (1-12)
    
    Returns:
        Dict with year, month, sessions count, total_hours, tasks, prs
    """
    with get_session() as db:
        sessions = (
            db.query(WorkSession)
            .filter(
                WorkSession.project_id == project_id,
                extract('year', WorkSession.session_date) == year,
                extract('month', WorkSession.session_date) == month
            )
            .all()
        )
        
        total_hours = sum(s.hours for s in sessions)
        all_tasks = []
        all_prs = []
        
        for s in sessions:
            tasks = json.loads(s.tasks_completed or '[]')
            prs = json.loads(s.prs_opened or '[]')
            all_tasks.extend(tasks)
            all_prs.extend(prs)
        
        return {
            'year': year,
            'month': month,
            'sessions': len(sessions),
            'total_hours': float(total_hours),
            'tasks_completed': all_tasks,
            'prs_opened': all_prs
        }


def parse_session_json(session: WorkSession) -> dict:
    """Convert a work session to a dict with parsed JSON fields.
    
    Args:
        session: WorkSession object
    
    Returns:
        Dict representation with parsed JSON
    """
    return {
        'id': session.id,
        'project_id': session.project_id,
        'session_date': session.session_date.isoformat(),
        'hours': float(session.hours),
        'tasks_completed': json.loads(session.tasks_completed or '[]'),
        'prs_opened': json.loads(session.prs_opened or '[]'),
        'notes': session.notes,
        'created_at': session.created_at.isoformat()
    }
