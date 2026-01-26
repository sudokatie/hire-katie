"""Test fixtures and configuration."""

import os
import pytest
from unittest.mock import MagicMock, patch

# Set test environment before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_fake"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_fake"
os.environ["ADMIN_PASSWORD"] = "testpassword"

from fastapi.testclient import TestClient

from src.config import reset_config, load_config
from src.utils.db import reset_db, init_db, get_session
from src.models import Client, ClientStatus, Project, ProjectStatus


@pytest.fixture(autouse=True)
def reset_state():
    """Reset config and database state before each test."""
    reset_config()
    reset_db()
    yield
    reset_config()
    reset_db()


@pytest.fixture
def config():
    """Load test configuration."""
    return load_config()


@pytest.fixture
def db_session():
    """Provide a database session for tests."""
    init_db()
    with get_session() as session:
        yield session


@pytest.fixture
def test_client():
    """Provide FastAPI test client."""
    from src.main import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_client(db_session):
    """Create a sample client in the database."""
    from src.services import create_client
    return create_client(
        email="test@example.com",
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        name="Test User"
    )


@pytest.fixture
def active_client(db_session):
    """Create an active client."""
    from src.services import activate_client
    return activate_client(
        email="active@example.com",
        stripe_customer_id="cus_active123",
        stripe_subscription_id="sub_active123",
        name="Active User"
    )


@pytest.fixture
def sample_project(active_client, db_session):
    """Create a sample project."""
    from src.services import IntakeData, create_project
    data = IntakeData(
        project_name="Test Project",
        repo_url="https://github.com/test/project",
        description="A test project",
        tech_stack="Python, FastAPI"
    )
    return create_project(active_client.id, data)


@pytest.fixture
def mock_stripe():
    """Mock Stripe API calls."""
    with patch('stripe.Webhook.construct_event') as mock_construct, \
         patch('stripe.Customer.retrieve') as mock_customer, \
         patch('stripe.billing_portal.Session.create') as mock_portal:
        
        mock_customer.return_value = {'email': 'test@example.com'}
        mock_portal.return_value = MagicMock(url='https://billing.stripe.com/session/test')
        
        yield {
            'construct_event': mock_construct,
            'customer': mock_customer,
            'portal': mock_portal
        }


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for himalaya CLI."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='',
            stderr=''
        )
        yield mock_run
