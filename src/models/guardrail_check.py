"""Guardrail check model."""

import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from .base import Base


class GuardrailStatus(enum.Enum):
    """Status of guardrail review."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GuardrailCheck(Base):
    """A guardrail review of a project."""
    
    __tablename__ = "guardrail_checks"
    
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    status = Column(
        Enum(GuardrailStatus),
        nullable=False,
        default=GuardrailStatus.PENDING
    )
    reason = Column(Text)  # Rejection reason if any
    checked_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="guardrail_checks")
    
    def __repr__(self) -> str:
        return f"<GuardrailCheck {self.status.value}>"
