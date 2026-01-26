"""Tests for Stripe service."""

import pytest
from unittest.mock import patch, MagicMock
import stripe

from src.services.stripe_service import (
    verify_webhook_signature,
    parse_webhook_event,
    get_customer_email,
    get_portal_url,
)


class TestVerifyWebhookSignature:
    def test_returns_true_for_valid_signature(self, mock_stripe):
        mock_stripe['construct_event'].return_value = {'type': 'test'}
        
        result = verify_webhook_signature(
            b'payload',
            'sig_header',
            'webhook_secret'
        )
        
        assert result is True

    def test_returns_false_for_invalid_signature(self, mock_stripe):
        mock_stripe['construct_event'].side_effect = stripe.error.SignatureVerificationError(
            'Invalid signature', 'sig_header'
        )
        
        result = verify_webhook_signature(
            b'payload',
            'bad_sig',
            'webhook_secret'
        )
        
        assert result is False


class TestParseWebhookEvent:
    def test_parses_subscription_created(self, mock_stripe):
        mock_stripe['construct_event'].return_value = {
            'type': 'customer.subscription.created',
            'data': {
                'object': {
                    'id': 'sub_123',
                    'customer': 'cus_123'
                }
            }
        }
        mock_stripe['customer'].return_value = {'email': 'test@example.com'}
        
        event = parse_webhook_event(b'payload', 'sig', 'secret')
        
        assert event is not None
        assert event.type == 'customer.subscription.created'
        assert event.subscription_id == 'sub_123'
        assert event.customer_id == 'cus_123'
        assert event.customer_email == 'test@example.com'

    def test_parses_invoice_event(self, mock_stripe):
        mock_stripe['construct_event'].return_value = {
            'type': 'invoice.payment_failed',
            'data': {
                'object': {
                    'customer': 'cus_123',
                    'subscription': 'sub_123',
                    'customer_email': 'test@example.com'
                }
            }
        }
        
        event = parse_webhook_event(b'payload', 'sig', 'secret')
        
        assert event.type == 'invoice.payment_failed'
        assert event.customer_email == 'test@example.com'

    def test_returns_none_for_invalid_signature(self, mock_stripe):
        mock_stripe['construct_event'].side_effect = stripe.error.SignatureVerificationError(
            'Invalid', 'sig'
        )
        
        event = parse_webhook_event(b'payload', 'bad_sig', 'secret')
        
        assert event is None


class TestGetCustomerEmail:
    def test_returns_email(self, mock_stripe):
        mock_stripe['customer'].return_value = {'email': 'customer@example.com'}
        
        email = get_customer_email('cus_123')
        
        assert email == 'customer@example.com'

    def test_returns_none_on_error(self, mock_stripe):
        mock_stripe['customer'].side_effect = stripe.error.StripeError('Not found')
        
        email = get_customer_email('cus_missing')
        
        assert email is None


class TestGetPortalUrl:
    def test_returns_url(self, mock_stripe):
        url = get_portal_url('cus_123', 'https://example.com')
        
        assert url == 'https://billing.stripe.com/session/test'

    def test_returns_none_on_error(self, mock_stripe):
        mock_stripe['portal'].side_effect = stripe.error.StripeError('Error')
        
        url = get_portal_url('cus_123', 'https://example.com')
        
        assert url is None
