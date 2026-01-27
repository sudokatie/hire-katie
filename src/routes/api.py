"""Public API routes."""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from ..config import get_config
from ..models.client import ClientStatus
from ..services import (
    IntakeData,
    create_checkout_session,
    create_project,
    get_client_by_email,
    list_projects,
    send_template,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class IntakeRequest(BaseModel):
    """Project intake form submission."""
    email: EmailStr
    project_name: str
    repo_url: Optional[str] = None
    description: Optional[str] = None
    tech_stack: Optional[str] = None
    access_method: Optional[str] = None
    coding_standards: Optional[str] = None
    do_not_touch: Optional[str] = None
    communication_preference: Optional[str] = None


class IntakeResponse(BaseModel):
    """Response to intake form submission."""
    success: bool
    message: str


class StatusResponse(BaseModel):
    """Subscription status response."""
    active: bool
    projects_count: int


@router.post("/api/intake", response_model=IntakeResponse)
async def submit_intake(data: IntakeRequest):
    """Submit a project intake form.
    
    Creates a project for the client if they have an active subscription.
    """
    logger.info(f"Intake submission from {data.email}: {data.project_name}")
    
    # Check if client exists
    client = get_client_by_email(data.email)
    
    if not client:
        # Client doesn't exist - they need to subscribe first
        logger.info(f"Intake from non-subscriber: {data.email}")
        return IntakeResponse(
            success=True,
            message="Thanks for your interest! Please subscribe first at blackabee.com/hire/pricing, then submit your project."
        )
    
    if client.status != ClientStatus.ACTIVE:
        # Client exists but subscription not active
        logger.info(f"Intake from inactive client: {data.email} ({client.status.value})")
        return IntakeResponse(
            success=True,
            message="Your subscription is not currently active. Please update your payment at the Stripe customer portal to submit projects."
        )
    
    # Create project
    intake_data = IntakeData(
        project_name=data.project_name,
        repo_url=data.repo_url,
        description=data.description,
        tech_stack=data.tech_stack,
        access_method=data.access_method,
        coding_standards=data.coding_standards,
        do_not_touch=data.do_not_touch,
        communication_preference=data.communication_preference
    )
    
    project = create_project(client.id, intake_data)
    logger.info(f"Created project {project.id}: {project.name} for {client.email}")
    
    # Send acknowledgment email
    send_template(
        to=client.email,
        template_name="intake_received",
        variables={
            "name": client.name or client.email,
            "project_name": project.name
        }
    )
    
    return IntakeResponse(
        success=True,
        message=f"Project '{project.name}' submitted! I'll review it and reach out within a few days."
    )


@router.get("/api/status/{email}", response_model=StatusResponse)
async def check_status(email: str):
    """Check subscription status for an email.
    
    Returns basic status info without exposing sensitive data.
    """
    client = get_client_by_email(email)
    
    if not client:
        return StatusResponse(active=False, projects_count=0)
    
    projects, _ = list_projects(client_id=client.id)
    
    return StatusResponse(
        active=client.status == ClientStatus.ACTIVE,
        projects_count=len(projects)
    )


class PortalRequest(BaseModel):
    """Request for Stripe portal URL."""
    email: EmailStr


class PortalResponse(BaseModel):
    """Response with Stripe portal URL."""
    success: bool
    portal_url: Optional[str] = None
    message: Optional[str] = None


@router.post("/api/portal", response_model=PortalResponse)
async def get_portal(data: PortalRequest):
    """Get Stripe customer portal URL for subscription management.
    
    Allows subscribers to manage their payment method and cancel.
    """
    from ..services import get_portal_url
    
    client = get_client_by_email(data.email)
    
    if not client:
        return PortalResponse(
            success=False,
            message="No subscription found for this email."
        )
    
    if not client.stripe_customer_id:
        return PortalResponse(
            success=False,
            message="No payment information on file."
        )
    
    portal_url = get_portal_url(
        client.stripe_customer_id,
        "https://blackabee.com/hire/success.html"
    )
    
    if not portal_url:
        return PortalResponse(
            success=False,
            message="Could not generate portal link. Please email blackabee@gmail.com for help."
        )
    
    return PortalResponse(
        success=True,
        portal_url=portal_url
    )


class CheckoutResponse(BaseModel):
    """Response with Stripe checkout URL."""
    success: bool
    checkout_url: Optional[str] = None
    message: Optional[str] = None


@router.post("/api/checkout", response_model=CheckoutResponse)
async def create_checkout():
    """Create a Stripe checkout session for subscription.
    
    Returns a URL to redirect the user to Stripe's hosted checkout page.
    """
    config = get_config()
    
    if not config.stripe.price_id:
        logger.error("Stripe price_id not configured")
        return CheckoutResponse(
            success=False,
            message="Payment system not configured. Please contact blackabee@gmail.com."
        )
    
    checkout_url = create_checkout_session(
        price_id=config.stripe.price_id,
        success_url="https://blackabee.com/hire/success.html?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://blackabee.com/hire/pricing.html"
    )
    
    if not checkout_url:
        return CheckoutResponse(
            success=False,
            message="Could not create checkout session. Please try again or contact blackabee@gmail.com."
        )
    
    logger.info("Created checkout session, redirecting to Stripe")
    return CheckoutResponse(
        success=True,
        checkout_url=checkout_url
    )
