"""Project model."""

import enum

from sqlalchemy import Column, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class ProjectStatus(enum.Enum):
    """Project lifecycle status."""
    INTAKE = "intake"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class Project(Base, TimestampMixin):
    """A client's project."""
    
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    repo_url = Column(String(500))
    description = Column(Text)
    tech_stack = Column(Text)
    access_method = Column(String(100))
    coding_standards = Column(Text)
    do_not_touch = Column(Text)
    communication_preference = Column(String(50))
    status = Column(
        Enum(ProjectStatus),
        nullable=False,
        default=ProjectStatus.INTAKE
    )
    
    # Relationships
    client = relationship("Client", back_populates="projects")
    work_sessions = relationship("WorkSession", back_populates="project", cascade="all, delete-orphan")
    guardrail_checks = relationship("GuardrailCheck", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.status.value})>"
