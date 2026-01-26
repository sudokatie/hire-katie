"""Stripe webhook handlers."""

import logging

from fastapi import APIRouter, HTTPException, Request

from ..config import get_config
from ..models.client import ClientStatus
from ..services import (
    StripeEvent,
    activate_client,
    get_client_by_stripe_id,
    get_portal_url,
    parse_webhook_event,
    send_template,
    update_client_status,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events.
    
    Verifies signature and processes subscription/invoice events.
    Always returns 200 to prevent retries (unless signature invalid).
    """
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature', '')
    
    config = get_config()
    event = parse_webhook_event(payload, sig_header, config.stripe.webhook_secret)
    
    if not event:
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    logger.info(f"Received Stripe event: {event.type}")
    
    try:
        if event.type == 'customer.subscription.created':
            _handle_subscription_created(event)
        elif event.type == 'customer.subscription.updated':
            _handle_subscription_updated(event)
        elif event.type == 'customer.subscription.deleted':
            _handle_subscription_deleted(event)
        elif event.type == 'invoice.payment_failed':
            _handle_payment_failed(event)
        elif event.type == 'invoice.payment_succeeded':
            _handle_payment_succeeded(event)
        else:
            logger.info(f"Ignoring event type: {event.type}")
    except Exception as e:
        # Log but don't fail - we want to return 200 to prevent retries
        logger.error(f"Error handling webhook {event.type}: {e}", exc_info=True)
    
    return {"status": "ok"}


def _handle_subscription_created(event: StripeEvent) -> None:
    """Handle new subscription.
    
    Creates or activates client and sends welcome email.
    """
    if not event.customer_email:
        logger.error("No customer email in subscription.created event")
        return
    
    client = activate_client(
        email=event.customer_email,
        stripe_customer_id=event.customer_id,
        stripe_subscription_id=event.subscription_id
    )
    
    logger.info(f"Activated client: {client.email}")
    
    # Send welcome email
    send_template(
        to=client.email,
        template_name="welcome",
        variables={"name": client.name or client.email}
    )


def _handle_subscription_updated(event: StripeEvent) -> None:
    """Handle subscription status change.
    
    Updates client status based on subscription status.
    """
    client = get_client_by_stripe_id(event.customer_id)
    if not client:
        logger.warning(f"No client for customer {event.customer_id}")
        return
    
    # Check subscription status in raw data
    status = event.raw_data.get('status')
    logger.info(f"Subscription status for {client.email}: {status}")
    
    if status == 'active':
        update_client_status(client.id, ClientStatus.ACTIVE)
    elif status in ('past_due', 'unpaid'):
        update_client_status(client.id, ClientStatus.PAUSED)
    elif status == 'canceled':
        update_client_status(client.id, ClientStatus.CANCELLED)


def _handle_subscription_deleted(event: StripeEvent) -> None:
    """Handle subscription cancellation.
    
    Marks client as cancelled and sends offboarding email.
    """
    client = get_client_by_stripe_id(event.customer_id)
    if not client:
        logger.warning(f"No client for customer {event.customer_id}")
        return
    
    update_client_status(client.id, ClientStatus.CANCELLED)
    logger.info(f"Cancelled client: {client.email}")
    
    send_template(
        to=client.email,
        template_name="subscription_cancelled",
        variables={"name": client.name or client.email}
    )


def _handle_payment_failed(event: StripeEvent) -> None:
    """Handle failed payment.
    
    Pauses client and sends notification with portal link.
    """
    client = get_client_by_stripe_id(event.customer_id)
    if not client:
        logger.warning(f"No client for customer {event.customer_id}")
        return
    
    update_client_status(client.id, ClientStatus.PAUSED)
    logger.info(f"Paused client due to payment failure: {client.email}")
    
    portal_url = get_portal_url(
        event.customer_id,
        "https://blackabee.com/hire"
    )
    
    send_template(
        to=client.email,
        template_name="payment_failed",
        variables={
            "name": client.name or client.email,
            "portal_url": portal_url or "https://blackabee.com/hire"
        }
    )


def _handle_payment_succeeded(event: StripeEvent) -> None:
    """Handle successful payment.
    
    Reactivates client if they were paused.
    """
    client = get_client_by_stripe_id(event.customer_id)
    if not client:
        return
    
    # Reactivate if was paused
    if client.status == ClientStatus.PAUSED:
        update_client_status(client.id, ClientStatus.ACTIVE)
        logger.info(f"Reactivated client after payment: {client.email}")
