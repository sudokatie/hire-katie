"""Tests for client service."""

import pytest

from src.models import ClientStatus
from src.services import (
    create_client,
    get_client_by_email,
    get_client_by_stripe_id,
    update_client_status,
    list_clients,
    activate_client,
)


class TestCreateClient:
    def test_creates_client_with_email(self, db_session):
        client = create_client(email="new@example.com")
        assert client.email == "new@example.com"
        assert client.status == ClientStatus.PENDING

    def test_creates_client_with_all_fields(self, db_session):
        client = create_client(
            email="full@example.com",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            name="Full User"
        )
        assert client.email == "full@example.com"
        assert client.stripe_customer_id == "cus_123"
        assert client.name == "Full User"

    def test_raises_on_duplicate_email(self, db_session):
        create_client(email="dupe@example.com")
        with pytest.raises(ValueError, match="already exists"):
            create_client(email="dupe@example.com")


class TestGetClient:
    def test_get_by_email_returns_client(self, sample_client):
        found = get_client_by_email("test@example.com")
        assert found is not None
        assert found.id == sample_client.id

    def test_get_by_email_returns_none_for_missing(self, db_session):
        found = get_client_by_email("missing@example.com")
        assert found is None

    def test_get_by_stripe_id_returns_client(self, sample_client):
        found = get_client_by_stripe_id("cus_test123")
        assert found is not None
        assert found.id == sample_client.id

    def test_get_by_stripe_id_returns_none_for_missing(self, db_session):
        found = get_client_by_stripe_id("cus_missing")
        assert found is None


class TestUpdateClientStatus:
    def test_updates_status(self, sample_client):
        updated = update_client_status(sample_client.id, ClientStatus.ACTIVE)
        assert updated.status == ClientStatus.ACTIVE

    def test_raises_for_missing_client(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            update_client_status(9999, ClientStatus.ACTIVE)


class TestListClients:
    def test_returns_all_clients(self, sample_client, active_client):
        clients, total = list_clients()
        assert total == 2
        assert len(clients) == 2

    def test_filters_by_status(self, sample_client, active_client):
        clients, total = list_clients(status=ClientStatus.ACTIVE)
        assert total == 1
        assert clients[0].status == ClientStatus.ACTIVE

    def test_pagination(self, db_session):
        for i in range(5):
            create_client(email=f"user{i}@example.com")
        
        clients, total = list_clients(page=1, limit=2)
        assert total == 5
        assert len(clients) == 2
        
        clients2, _ = list_clients(page=2, limit=2)
        assert len(clients2) == 2


class TestActivateClient:
    def test_creates_new_active_client(self, db_session):
        client = activate_client(
            email="brand_new@example.com",
            stripe_customer_id="cus_new",
            stripe_subscription_id="sub_new"
        )
        assert client.status == ClientStatus.ACTIVE
        assert client.stripe_customer_id == "cus_new"

    def test_updates_existing_client(self, sample_client):
        updated = activate_client(
            email="test@example.com",
            stripe_customer_id="cus_updated",
            stripe_subscription_id="sub_updated"
        )
        assert updated.id == sample_client.id
        assert updated.status == ClientStatus.ACTIVE
        assert updated.stripe_customer_id == "cus_updated"
