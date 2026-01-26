"""Project management service."""

from dataclasses import dataclass
from typing import Optional

from ..models.client import Client
from ..models.guardrail_check import GuardrailCheck, GuardrailStatus
from ..models.project import Project, ProjectStatus
from ..models.work_session import WorkSession
from ..utils.db import get_session


@dataclass
class IntakeData:
    """Data from project intake form."""
    project_name: str
    repo_url: Optional[str] = None
    description: Optional[str] = None
    tech_stack: Optional[str] = None
    access_method: Optional[str] = None
    coding_standards: Optional[str] = None
    do_not_touch: Optional[str] = None
    communication_preference: Optional[str] = None


def create_project(client_id: int, data: IntakeData) -> Project:
    """Create a new project for a client.
    
    Args:
        client_id: ID of the owning client
        data: Project intake data
    
    Returns:
        The created project
    
    Raises:
        ValueError: If client not found
    """
    with get_session() as session:
        client = session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        project = Project(
            client_id=client_id,
            name=data.project_name,
            repo_url=data.repo_url,
            description=data.description,
            tech_stack=data.tech_stack,
            access_method=data.access_method,
            coding_standards=data.coding_standards,
            do_not_touch=data.do_not_touch,
            communication_preference=data.communication_preference,
            status=ProjectStatus.INTAKE
        )
        session.add(project)
        session.flush()  # Get project ID
        
        # Create initial guardrail check
        check = GuardrailCheck(
            project_id=project.id,
            status=GuardrailStatus.PENDING
        )
        session.add(check)
        
        session.commit()
        session.refresh(project)
        session.expunge(project)
        return project


def create_project_from_intake(email: str, data: IntakeData) -> Optional[Project]:
    """Create a project for a client identified by email.
    
    Args:
        email: Client email address
        data: Project intake data
    
    Returns:
        The created project, or None if client not found
    """
    with get_session() as session:
        client = session.query(Client).filter_by(email=email).first()
        if not client:
            return None
        
        project = Project(
            client_id=client.id,
            name=data.project_name,
            repo_url=data.repo_url,
            description=data.description,
            tech_stack=data.tech_stack,
            access_method=data.access_method,
            coding_standards=data.coding_standards,
            do_not_touch=data.do_not_touch,
            communication_preference=data.communication_preference,
            status=ProjectStatus.INTAKE
        )
        session.add(project)
        session.flush()
        
        check = GuardrailCheck(
            project_id=project.id,
            status=GuardrailStatus.PENDING
        )
        session.add(check)
        
        session.commit()
        session.refresh(project)
        session.expunge(project)
        return project


def get_project(project_id: int) -> Optional[Project]:
    """Get a project by ID.
    
    Args:
        project_id: Project ID
    
    Returns:
        Project if found, None otherwise
    """
    with get_session() as session:
        project = session.get(Project, project_id)
        if project:
            session.expunge(project)
        return project


def get_project_with_sessions(project_id: int) -> Optional[tuple[Project, list[WorkSession]]]:
    """Get a project with its work sessions.
    
    Args:
        project_id: Project ID
    
    Returns:
        Tuple of (project, sessions list) or None if not found
    """
    with get_session() as session:
        project = session.get(Project, project_id)
        if not project:
            return None
        
        sessions = (
            session.query(WorkSession)
            .filter_by(project_id=project_id)
            .order_by(WorkSession.session_date.desc())
            .all()
        )
        
        session.expunge(project)
        for s in sessions:
            session.expunge(s)
        
        return project, sessions


def update_project_status(project_id: int, status: ProjectStatus) -> Project:
    """Update a project's status.
    
    Args:
        project_id: Project ID
        status: New status
    
    Returns:
        Updated project
    
    Raises:
        ValueError: If project not found
    """
    with get_session() as session:
        project = session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        project.status = status
        session.commit()
        session.refresh(project)
        session.expunge(project)
        return project


def approve_project(project_id: int) -> Project:
    """Approve a project after guardrail review.
    
    Args:
        project_id: Project ID
    
    Returns:
        Updated project
    
    Raises:
        ValueError: If project not found
    """
    with get_session() as session:
        project = session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Update or create guardrail check
        check = (
            session.query(GuardrailCheck)
            .filter_by(project_id=project_id)
            .order_by(GuardrailCheck.checked_at.desc())
            .first()
        )
        
        if check:
            check.status = GuardrailStatus.APPROVED
        else:
            check = GuardrailCheck(
                project_id=project_id,
                status=GuardrailStatus.APPROVED
            )
            session.add(check)
        
        project.status = ProjectStatus.ACTIVE
        session.commit()
        session.refresh(project)
        session.expunge(project)
        return project


def reject_project(project_id: int, reason: str) -> Project:
    """Reject a project with a reason.
    
    Args:
        project_id: Project ID
        reason: Rejection reason
    
    Returns:
        Updated project
    
    Raises:
        ValueError: If project not found
    """
    with get_session() as session:
        project = session.get(Project, project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        check = (
            session.query(GuardrailCheck)
            .filter_by(project_id=project_id)
            .order_by(GuardrailCheck.checked_at.desc())
            .first()
        )
        
        if check:
            check.status = GuardrailStatus.REJECTED
            check.reason = reason
        else:
            check = GuardrailCheck(
                project_id=project_id,
                status=GuardrailStatus.REJECTED,
                reason=reason
            )
            session.add(check)
        
        project.status = ProjectStatus.PAUSED
        session.commit()
        session.refresh(project)
        session.expunge(project)
        return project


def list_projects(
    status: Optional[ProjectStatus] = None,
    client_id: Optional[int] = None,
    page: int = 1,
    limit: int = 20
) -> tuple[list[Project], int]:
    """List projects with optional filtering and pagination.
    
    Args:
        status: Filter by status (optional)
        client_id: Filter by client (optional)
        page: Page number (1-indexed)
        limit: Items per page
    
    Returns:
        Tuple of (projects list, total count)
    """
    with get_session() as session:
        query = session.query(Project)
        
        if status is not None:
            query = query.filter_by(status=status)
        if client_id is not None:
            query = query.filter_by(client_id=client_id)
        
        total = query.count()
        
        projects = (
            query
            .order_by(Project.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        
        for project in projects:
            session.expunge(project)
        
        return projects, total
