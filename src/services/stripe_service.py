"""Stripe API integration."""

import logging
from dataclasses import dataclass
from typing import Optional

import stripe

logger = logging.getLogger(__name__)


@dataclass
class StripeEvent:
    """Parsed Stripe webhook event."""
    type: str
    customer_id: Optional[str]
    customer_email: Optional[str]
    subscription_id: Optional[str]
    raw_data: dict


def init_stripe(secret_key: str) -> None:
    """Initialize Stripe with API key.
    
    Args:
        secret_key: Stripe secret API key
    """
    stripe.api_key = secret_key


def verify_webhook_signature(
    payload: bytes,
    sig_header: str,
    webhook_secret: str
) -> bool:
    """Verify a Stripe webhook signature.
    
    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header value
        webhook_secret: Webhook signing secret
    
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        return True
    except (stripe.error.SignatureVerificationError, ValueError) as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        return False


def parse_webhook_event(
    payload: bytes,
    sig_header: str,
    webhook_secret: str
) -> Optional[StripeEvent]:
    """Parse and validate a Stripe webhook event.
    
    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header value
        webhook_secret: Webhook signing secret
    
    Returns:
        StripeEvent if valid, None if signature invalid
    """
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (stripe.error.SignatureVerificationError, ValueError) as e:
        logger.warning(f"Webhook parsing failed: {e}")
        return None
    
    event_type = event['type']
    data = event['data']['object']
    
    customer_id = None
    customer_email = None
    subscription_id = None
    
    if event_type.startswith('customer.subscription'):
        # Subscription events
        subscription_id = data.get('id')
        customer_id = data.get('customer')
        # Email not in subscription, need to fetch
        if customer_id:
            customer_email = get_customer_email(customer_id)
    elif event_type.startswith('invoice'):
        # Invoice events
        customer_id = data.get('customer')
        subscription_id = data.get('subscription')
        customer_email = data.get('customer_email')
    elif event_type.startswith('customer'):
        # Customer events
        customer_id = data.get('id')
        customer_email = data.get('email')
    
    return StripeEvent(
        type=event_type,
        customer_id=customer_id,
        customer_email=customer_email,
        subscription_id=subscription_id,
        raw_data=data
    )


def get_customer_email(customer_id: str) -> Optional[str]:
    """Get customer email from Stripe.
    
    Args:
        customer_id: Stripe customer ID
    
    Returns:
        Email address if found, None otherwise
    """
    try:
        customer = stripe.Customer.retrieve(customer_id)
        return customer.get('email')
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve customer {customer_id}: {e}")
        return None


def get_portal_url(customer_id: str, return_url: str) -> Optional[str]:
    """Get Stripe customer portal URL.
    
    Args:
        customer_id: Stripe customer ID
        return_url: URL to redirect to after portal
    
    Returns:
        Portal URL if successful, None otherwise
    """
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
        return session.url
    except stripe.error.StripeError as e:
        logger.error(f"Failed to create portal session: {e}")
        return None


def get_subscription_status(subscription_id: str) -> Optional[str]:
    """Get subscription status from Stripe.
    
    Args:
        subscription_id: Stripe subscription ID
    
    Returns:
        Status string (active, past_due, canceled, etc.) or None
    """
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return subscription.get('status')
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
        return None


def create_checkout_session(
    price_id: str,
    success_url: str,
    cancel_url: str
) -> Optional[str]:
    """Create a Stripe Checkout session for subscription.
    
    Args:
        price_id: Stripe price ID for the subscription
        success_url: URL to redirect to on successful payment
        cancel_url: URL to redirect to if user cancels
    
    Returns:
        Checkout session URL if successful, None otherwise
    """
    try:
        session = stripe.checkout.Session.create(
            mode='subscription',
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
        )
        logger.info(f"Created checkout session: {session.id}")
        return session.url
    except stripe.error.StripeError as e:
        logger.error(f"Failed to create checkout session: {e}")
        return None
