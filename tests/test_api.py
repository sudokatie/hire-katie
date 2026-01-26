"""Tests for public API routes."""

import pytest
from unittest.mock import patch


class TestIntakeEndpoint:
    def test_creates_project_for_active_client(self, test_client, active_client):
        with patch('src.routes.api.send_template'):
            response = test_client.post(
                "/api/intake",
                json={
                    "email": "active@example.com",
                    "project_name": "API Test Project",
                    "description": "Testing the intake API"
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "submitted" in data["message"].lower()

    def test_returns_message_for_nonexistent_client(self, test_client, db_session):
        response = test_client.post(
            "/api/intake",
            json={
                "email": "nobody@example.com",
                "project_name": "Orphan Project"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "subscribe" in data["message"].lower()

    def test_validates_email_format(self, test_client):
        response = test_client.post(
            "/api/intake",
            json={
                "email": "not-an-email",
                "project_name": "Test"
            }
        )
        
        assert response.status_code == 422

    def test_requires_project_name(self, test_client):
        response = test_client.post(
            "/api/intake",
            json={
                "email": "test@example.com"
            }
        )
        
        assert response.status_code == 422


class TestStatusEndpoint:
    def test_returns_active_for_active_client(self, test_client, active_client):
        response = test_client.get(f"/api/status/{active_client.email}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True

    def test_returns_inactive_for_missing_client(self, test_client, db_session):
        response = test_client.get("/api/status/nobody@example.com")
        
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False
        assert data["projects_count"] == 0


class TestHealthEndpoint:
    def test_returns_ok(self, test_client):
        response = test_client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
