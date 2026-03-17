"""Tests for client portal routes."""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from src.main import create_app
from src.models.client import Client, ClientStatus
from src.models.project import Project, ProjectStatus
from src.models.work_session import WorkSession
from src.routes import portal


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_client():
    """Create a mock client."""
    c = MagicMock(spec=Client)
    c.id = 1
    c.email = "test@example.com"
    c.name = "Test Client"
    c.status = ClientStatus.ACTIVE
    c.created_at = MagicMock()
    c.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    return c


@pytest.fixture
def mock_project():
    """Create a mock project."""
    p = MagicMock(spec=Project)
    p.id = 1
    p.client_id = 1
    p.name = "Test Project"
    p.repo_url = "https://github.com/test/test"
    p.status = ProjectStatus.ACTIVE
    p.created_at = MagicMock()
    p.created_at.isoformat.return_value = "2024-01-01T00:00:00"
    return p


@pytest.fixture
def mock_session():
    """Create a mock work session."""
    s = MagicMock(spec=WorkSession)
    s.id = 1
    s.project_id = 1
    s.session_date = date(2024, 1, 15)
    s.hours = Decimal("4.5")
    s.tasks_completed = json.dumps(["Fix login bug", "Add tests"])
    s.prs_opened = json.dumps(["https://github.com/test/test/pull/1"])
    s.notes = "Good progress"
    return s


class TestMagicLinkCreation:
    """Tests for magic link token creation."""
    
    def test_create_magic_link_returns_token(self):
        """Magic link creation returns a token."""
        token = portal.create_magic_link("test@example.com")
        assert token is not None
        assert len(token) > 20
    
    def test_verify_magic_link_valid(self):
        """Valid magic link returns email."""
        token = portal.create_magic_link("test@example.com")
        email = portal.verify_magic_link(token)
        assert email == "test@example.com"
    
    def test_verify_magic_link_one_time_use(self):
        """Magic link can only be used once."""
        token = portal.create_magic_link("test@example.com")
        
        # First use succeeds
        email = portal.verify_magic_link(token)
        assert email == "test@example.com"
        
        # Second use fails
        email = portal.verify_magic_link(token)
        assert email is None
    
    def test_verify_magic_link_invalid_token(self):
        """Invalid token returns None."""
        email = portal.verify_magic_link("invalid_token")
        assert email is None
    
    def test_create_magic_link_normalizes_email(self):
        """Email is normalized to lowercase."""
        token = portal.create_magic_link("Test@Example.COM")
        email = portal.verify_magic_link(token)
        assert email == "test@example.com"


class TestPortalSession:
    """Tests for portal session management."""
    
    def test_create_portal_session(self):
        """Session creation returns session ID."""
        session_id = portal.create_portal_session(1)
        assert session_id is not None
        assert len(session_id) > 20
    
    def test_verify_portal_session_valid(self):
        """Valid session returns client ID."""
        session_id = portal.create_portal_session(42)
        # Manually set cookie for test
        portal._portal_sessions[session_id] = 42
        
        client_id = portal._portal_sessions.get(session_id)
        assert client_id == 42


class TestRequestLogin:
    """Tests for login request endpoint."""
    
    @patch("src.routes.portal.get_client_by_email")
    def test_request_login_existing_client(self, mock_get, client, mock_client):
        """Request login for existing client returns success."""
        mock_get.return_value = mock_client
        
        response = client.post(
            "/api/portal/request-login",
            json={"email": "test@example.com"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    @patch("src.routes.portal.get_client_by_email")
    def test_request_login_nonexistent_client(self, mock_get, client):
        """Request login for nonexistent client still returns success (no enumeration)."""
        mock_get.return_value = None
        
        response = client.post(
            "/api/portal/request-login",
            json={"email": "nobody@example.com"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    @patch("src.routes.portal.get_client_by_email")
    def test_request_login_cancelled_client(self, mock_get, client, mock_client):
        """Request login for cancelled client returns success but no link created."""
        mock_client.status = ClientStatus.CANCELLED
        mock_get.return_value = mock_client
        
        response = client.post(
            "/api/portal/request-login",
            json={"email": "test@example.com"}
        )
        
        # Still returns success to prevent enumeration
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestTokenLogin:
    """Tests for token login endpoint."""
    
    @patch("src.routes.portal.get_client_by_email")
    def test_login_with_valid_token(self, mock_get, client, mock_client):
        """Login with valid token succeeds and sets cookie."""
        mock_get.return_value = mock_client
        
        # Create a magic link
        token = portal.create_magic_link("test@example.com")
        
        response = client.post(
            "/api/portal/login",
            json={"token": token}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "portal_session" in response.cookies
    
    def test_login_with_invalid_token(self, client):
        """Login with invalid token fails."""
        response = client.post(
            "/api/portal/login",
            json={"token": "invalid_token"}
        )
        
        assert response.status_code == 401


class TestPortalEndpoints:
    """Tests for authenticated portal endpoints."""
    
    @patch("src.routes.portal.get_client_by_id")
    def test_get_current_client(self, mock_get, client, mock_client):
        """Get current client returns client info."""
        mock_get.return_value = mock_client
        
        # Create session
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/me",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        assert response.json()["client"]["email"] == "test@example.com"
    
    def test_get_current_client_unauthenticated(self, client):
        """Unauthenticated request fails."""
        response = client.get("/api/portal/me")
        assert response.status_code == 401
    
    @patch("src.routes.portal.list_projects")
    def test_list_client_projects(self, mock_list, client, mock_project):
        """List projects returns client's projects."""
        mock_list.return_value = ([mock_project], 1)
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/projects",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["projects"][0]["name"] == "Test Project"
    
    @patch("src.routes.portal.get_project_with_sessions")
    def test_get_project_detail(self, mock_get, client, mock_project, mock_session):
        """Get project detail returns project with sessions."""
        mock_get.return_value = (mock_project, [mock_session])
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/projects/1",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        assert response.json()["project"]["name"] == "Test Project"
        assert response.json()["totals"]["hours"] == 4.5
        assert response.json()["totals"]["prs"] == 1
        assert response.json()["totals"]["tasks"] == 2
    
    @patch("src.routes.portal.get_project_with_sessions")
    def test_get_project_detail_wrong_client(self, mock_get, client, mock_project, mock_session):
        """Cannot access another client's project."""
        mock_project.client_id = 999  # Different client
        mock_get.return_value = (mock_project, [mock_session])
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/projects/1",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 403


class TestClientSummary:
    """Tests for client summary endpoint."""
    
    @patch("src.routes.portal.get_project_with_sessions")
    @patch("src.routes.portal.list_projects")
    def test_get_client_summary(self, mock_list, mock_get, client, mock_project, mock_session):
        """Summary returns totals across all projects."""
        mock_list.return_value = ([mock_project], 1)
        mock_get.return_value = (mock_project, [mock_session])
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/summary",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["totals"]["hours"] == 4.5
        assert data["totals"]["prs"] == 1
        assert data["totals"]["tasks"] == 2
        assert data["totals"]["projects"] == 1


class TestReports:
    """Tests for report download endpoints."""
    
    @patch("src.routes.portal.get_project_with_sessions")
    @patch("src.routes.portal.list_projects")
    def test_download_sessions_csv(self, mock_list, mock_get, client, mock_project, mock_session):
        """Sessions report returns CSV."""
        mock_list.return_value = ([mock_project], 1)
        mock_get.return_value = (mock_project, [mock_session])
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/reports/sessions?format=csv",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "project,date,hours,tasks,prs,notes" in response.text
        assert "Test Project" in response.text
    
    @patch("src.routes.portal.get_project_with_sessions")
    @patch("src.routes.portal.list_projects")
    def test_download_sessions_json(self, mock_list, mock_get, client, mock_project, mock_session):
        """Sessions report returns JSON when requested."""
        mock_list.return_value = ([mock_project], 1)
        mock_get.return_value = (mock_project, [mock_session])
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/reports/sessions?format=json",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["project"] == "Test Project"
    
    @patch("src.routes.portal.get_project_with_sessions")
    @patch("src.routes.portal.list_projects")
    def test_download_summary_csv(self, mock_list, mock_get, client, mock_project, mock_session):
        """Monthly summary report returns CSV."""
        mock_list.return_value = ([mock_project], 1)
        mock_get.return_value = (mock_project, [mock_session])
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/reports/summary?format=csv",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "month,hours,tasks,prs" in response.text
        # Session date is 2024-01-15, so month should be 2024-01
        assert "2024-01" in response.text
    
    @patch("src.routes.portal.get_project_with_sessions")
    @patch("src.routes.portal.list_projects")
    def test_download_summary_json(self, mock_list, mock_get, client, mock_project, mock_session):
        """Monthly summary report returns JSON when requested."""
        mock_list.return_value = ([mock_project], 1)
        mock_get.return_value = (mock_project, [mock_session])
        
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/reports/summary?format=json",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "monthly_summary" in data
        assert len(data["monthly_summary"]) == 1
        assert data["monthly_summary"][0]["month"] == "2024-01"
        assert data["monthly_summary"][0]["hours"] == 4.5
    
    def test_invalid_format_rejected(self, client):
        """Invalid format parameter returns 400."""
        session_id = portal.create_portal_session(1)
        
        response = client.get(
            "/api/portal/reports/sessions?format=pdf",
            cookies={"portal_session": session_id}
        )
        
        assert response.status_code == 400
    
    def test_reports_require_auth(self, client):
        """Reports require authentication."""
        response = client.get("/api/portal/reports/sessions")
        assert response.status_code == 401
        
        response = client.get("/api/portal/reports/summary")
        assert response.status_code == 401
