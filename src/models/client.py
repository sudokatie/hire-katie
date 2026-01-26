"""Client model."""

import enum

from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class ClientStatus(enum.Enum):
    """Client subscription status."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class Client(Base, TimestampMixin):
    """A subscribed client."""
    
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    stripe_customer_id = Column(String(255), unique=True, index=True)
    stripe_subscription_id = Column(String(255), unique=True)
    name = Column(String(255))
    status = Column(
        Enum(ClientStatus),
        nullable=False,
        default=ClientStatus.PENDING
    )
    
    # Relationships
    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")
    communications = relationship("Communication", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Client {self.email} ({self.status.value})>"
