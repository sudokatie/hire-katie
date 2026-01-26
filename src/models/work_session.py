"""Work session model."""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.orm import relationship

from .base import Base


class WorkSession(Base):
    """A logged work session on a project."""
    
    __tablename__ = "work_sessions"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    session_date = Column(Date, nullable=False)
    hours = Column(Numeric(4, 2), nullable=False)
    tasks_completed = Column(Text)  # JSON array
    prs_opened = Column(Text)  # JSON array
    notes = Column(Text)
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="work_sessions")
    
    def __repr__(self) -> str:
        return f"<WorkSession {self.session_date} ({self.hours}h)>"
