"""Tests for webhook routes."""

import pytest
from unittest.mock import patch, MagicMock


class TestStripeWebhook:
    def test_rejects_invalid_signature(self, test_client, mock_stripe):
        mock_stripe['construct_event'].side_effect = Exception("Invalid")
        
        response = test_client.post(
            "/api/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "invalid"}
        )
        
        assert response.status_code == 400

    def test_handles_subscription_created(self, test_client, mock_stripe, db_session):
        mock_stripe['construct_event'].return_value = {
            'type': 'customer.subscription.created',
            'data': {
                'object': {
                    'id': 'sub_new',
                    'customer': 'cus_new'
                }
            }
        }
        mock_stripe['customer'].return_value = {'email': 'new@example.com'}
        
        with patch('src.routes.webhooks.send_template') as mock_send:
            response = test_client.post(
                "/api/webhooks/stripe",
                content=b'{}',
                headers={"Stripe-Signature": "valid"}
            )
        
        assert response.status_code == 200
        
        # Verify client was created
        from src.services import get_client_by_email
        client = get_client_by_email('new@example.com')
        assert client is not None

    def test_handles_unknown_event(self, test_client, mock_stripe):
        mock_stripe['construct_event'].return_value = {
            'type': 'unknown.event.type',
            'data': {'object': {}}
        }
        
        response = test_client.post(
            "/api/webhooks/stripe",
            content=b'{}',
            headers={"Stripe-Signature": "valid"}
        )
        
        # Should return 200 even for unknown events
        assert response.status_code == 200

    def test_handles_subscription_deleted(self, test_client, mock_stripe, active_client):
        mock_stripe['construct_event'].return_value = {
            'type': 'customer.subscription.deleted',
            'data': {
                'object': {
                    'id': 'sub_active123',
                    'customer': 'cus_active123'
                }
            }
        }
        
        with patch('src.routes.webhooks.send_template') as mock_send:
            response = test_client.post(
                "/api/webhooks/stripe",
                content=b'{}',
                headers={"Stripe-Signature": "valid"}
            )
        
        assert response.status_code == 200
        
        # Verify client was cancelled
        from src.services import get_client_by_email
        from src.models import ClientStatus
        client = get_client_by_email('active@example.com')
        assert client.status == ClientStatus.CANCELLED

    def test_handles_payment_failed(self, test_client, mock_stripe, active_client):
        mock_stripe['construct_event'].return_value = {
            'type': 'invoice.payment_failed',
            'data': {
                'object': {
                    'customer': 'cus_active123',
                    'subscription': 'sub_active123',
                    'customer_email': 'active@example.com'
                }
            }
        }
        
        with patch('src.routes.webhooks.send_template') as mock_send:
            response = test_client.post(
                "/api/webhooks/stripe",
                content=b'{}',
                headers={"Stripe-Signature": "valid"}
            )
        
        assert response.status_code == 200
        
        # Verify client was paused
        from src.services import get_client_by_email
        from src.models import ClientStatus
        client = get_client_by_email('active@example.com')
        assert client.status == ClientStatus.PAUSED
