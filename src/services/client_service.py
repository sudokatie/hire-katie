"""Client management service."""

from typing import Optional

from ..models.client import Client, ClientStatus
from ..utils.db import get_session


def create_client(
    email: str,
    stripe_customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    name: Optional[str] = None
) -> Client:
    """Create a new client.
    
    Args:
        email: Client email address (must be unique)
        stripe_customer_id: Stripe customer ID
        stripe_subscription_id: Stripe subscription ID
        name: Client name
    
    Returns:
        The created client
    
    Raises:
        ValueError: If client with email already exists
    """
    with get_session() as session:
        existing = session.query(Client).filter_by(email=email).first()
        if existing:
            raise ValueError(f"Client with email {email} already exists")
        
        client = Client(
            email=email,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            name=name,
            status=ClientStatus.PENDING
        )
        session.add(client)
        session.commit()
        session.refresh(client)
        
        # Detach from session for return
        session.expunge(client)
        return client


def get_client_by_email(email: str) -> Optional[Client]:
    """Get a client by email address.
    
    Args:
        email: Email to search for
    
    Returns:
        Client if found, None otherwise
    """
    with get_session() as session:
        client = session.query(Client).filter_by(email=email).first()
        if client:
            session.expunge(client)
        return client


def get_client_by_stripe_id(stripe_customer_id: str) -> Optional[Client]:
    """Get a client by Stripe customer ID.
    
    Args:
        stripe_customer_id: Stripe customer ID to search for
    
    Returns:
        Client if found, None otherwise
    """
    with get_session() as session:
        client = session.query(Client).filter_by(stripe_customer_id=stripe_customer_id).first()
        if client:
            session.expunge(client)
        return client


def get_client_by_id(client_id: int) -> Optional[Client]:
    """Get a client by ID.
    
    Args:
        client_id: Client ID to search for
    
    Returns:
        Client if found, None otherwise
    """
    with get_session() as session:
        client = session.get(Client, client_id)
        if client:
            session.expunge(client)
        return client


def update_client_status(client_id: int, status: ClientStatus) -> Client:
    """Update a client's status.
    
    Args:
        client_id: ID of client to update
        status: New status
    
    Returns:
        Updated client
    
    Raises:
        ValueError: If client not found
    """
    with get_session() as session:
        client = session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        client.status = status
        session.commit()
        session.refresh(client)
        session.expunge(client)
        return client


def update_client_stripe(
    client_id: int,
    customer_id: Optional[str] = None,
    subscription_id: Optional[str] = None
) -> Client:
    """Update a client's Stripe IDs.
    
    Args:
        client_id: ID of client to update
        customer_id: New Stripe customer ID (if provided)
        subscription_id: New Stripe subscription ID (if provided)
    
    Returns:
        Updated client
    
    Raises:
        ValueError: If client not found
    """
    with get_session() as session:
        client = session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        if customer_id is not None:
            client.stripe_customer_id = customer_id
        if subscription_id is not None:
            client.stripe_subscription_id = subscription_id
        
        session.commit()
        session.refresh(client)
        session.expunge(client)
        return client


def list_clients(
    status: Optional[ClientStatus] = None,
    page: int = 1,
    limit: int = 20
) -> tuple[list[Client], int]:
    """List clients with optional filtering and pagination.
    
    Args:
        status: Filter by status (optional)
        page: Page number (1-indexed)
        limit: Items per page
    
    Returns:
        Tuple of (clients list, total count)
    """
    with get_session() as session:
        query = session.query(Client)
        
        if status is not None:
            query = query.filter_by(status=status)
        
        total = query.count()
        
        clients = (
            query
            .order_by(Client.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )
        
        for client in clients:
            session.expunge(client)
        
        return clients, total


def activate_client(
    email: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    name: Optional[str] = None
) -> Client:
    """Create or update a client to active status.
    
    Used by webhook handler when subscription is created.
    
    Args:
        email: Client email
        stripe_customer_id: Stripe customer ID
        stripe_subscription_id: Stripe subscription ID
        name: Client name (optional)
    
    Returns:
        The activated client
    """
    with get_session() as session:
        client = session.query(Client).filter_by(email=email).first()
        
        if client:
            # Update existing
            client.stripe_customer_id = stripe_customer_id
            client.stripe_subscription_id = stripe_subscription_id
            client.status = ClientStatus.ACTIVE
            if name:
                client.name = name
        else:
            # Create new
            client = Client(
                email=email,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                name=name,
                status=ClientStatus.ACTIVE
            )
            session.add(client)
        
        session.commit()
        session.refresh(client)
        session.expunge(client)
        return client
