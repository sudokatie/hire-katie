"""SQLAlchemy base and common utilities."""

from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""
    
    created_at = Column(
        DateTime,
        nullable=False,
        default=func.now()
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now()
    )
