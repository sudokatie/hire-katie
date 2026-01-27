"""Tests for admin routes."""

import pytest


class TestAdminLogin:
    """Tests for admin login."""

    def test_login_with_correct_password(self, test_client):
        """Should set session cookie on correct password."""
        response = test_client.post(
            "/api/admin/login",
            json={"password": "testpassword"}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "admin_session" in response.cookies

    def test_login_with_wrong_password(self, test_client):
        """Should return 401 on wrong password."""
        response = test_client.post(
            "/api/admin/login",
            json={"password": "wrongpassword"}
        )
        
        assert response.status_code == 401

    def test_login_without_password(self, test_client):
        """Should return 422 when password missing."""
        response = test_client.post(
            "/api/admin/login",
            json={}
        )
        
        assert response.status_code == 422


class TestAdminAuth:
    """Tests for admin authentication requirement."""

    def test_clients_requires_auth(self, test_client):
        """Should return 401 when not authenticated."""
        response = test_client.get("/api/admin/clients")
        assert response.status_code == 401

    def test_projects_requires_auth(self, test_client):
        """Should return 401 when not authenticated."""
        response = test_client.get("/api/admin/projects")
        assert response.status_code == 401

    def test_stats_requires_auth(self, test_client):
        """Should return 401 when not authenticated."""
        response = test_client.get("/api/admin/stats")
        assert response.status_code == 401


class TestAdminEndpoints:
    """Tests for admin endpoints when authenticated."""

    @pytest.fixture
    def auth_client(self, test_client):
        """Get an authenticated test client."""
        test_client.post(
            "/api/admin/login",
            json={"password": "testpassword"}
        )
        return test_client

    def test_list_clients(self, auth_client, sample_client):
        """Should return list of clients."""
        response = auth_client.get("/api/admin/clients")
        
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert "total" in data

    def test_list_projects(self, auth_client, sample_project):
        """Should return list of projects."""
        response = auth_client.get("/api/admin/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total" in data

    def test_get_stats(self, auth_client, active_client):
        """Should return dashboard stats."""
        response = auth_client.get("/api/admin/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert "projects" in data

    def test_approve_project(self, auth_client, sample_project):
        """Should approve a project."""
        response = auth_client.post(f"/api/admin/projects/{sample_project.id}/approve")
        
        assert response.status_code == 200
        data = response.json()
        assert data["project"]["status"] == "active"

    def test_reject_project(self, auth_client, sample_project):
        """Should reject a project with reason."""
        response = auth_client.post(
            f"/api/admin/projects/{sample_project.id}/reject",
            json={"reason": "Violates guardrails"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["project"]["status"] == "paused"

    def test_logout(self, auth_client):
        """Should clear session on logout."""
        response = auth_client.post("/api/admin/logout")
        
        assert response.status_code == 200
        
        # Verify no longer authenticated
        response = auth_client.get("/api/admin/clients")
        assert response.status_code == 401
