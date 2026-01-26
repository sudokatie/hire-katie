"""Communication model."""

import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from .base import Base


class CommunicationDirection(enum.Enum):
    """Direction of communication."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Communication(Base):
    """A logged email communication with a client."""
    
    __tablename__ = "communications"
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    direction = Column(Enum(CommunicationDirection), nullable=False)
    subject = Column(String(500))
    content = Column(Text)
    message_id = Column(String(255))  # For email threading
    created_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationships
    client = relationship("Client", back_populates="communications")
    
    def __repr__(self) -> str:
        return f"<Communication {self.direction.value}: {self.subject[:30] if self.subject else 'No subject'}>"
