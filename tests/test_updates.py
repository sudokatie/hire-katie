"""Tests for automated update service."""

import json
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.models.client import Client, ClientStatus
from src.models.project import Project, ProjectStatus
from src.models.work_session import WorkSession
from src.services.update_service import (
    ClientUpdate,
    ProjectUpdate,
    format_update_text,
    get_client_update,
    send_client_update,
)


@pytest.fixture
def mock_client():
    """Create a mock client."""
    c = MagicMock(spec=Client)
    c.id = 1
    c.email = "test@example.com"
    c.name = "Test Client"
    c.status = ClientStatus.ACTIVE
    return c


@pytest.fixture
def mock_project():
    """Create a mock project."""
    p = MagicMock(spec=Project)
    p.id = 1
    p.client_id = 1
    p.name = "Test Project"
    p.status = ProjectStatus.ACTIVE
    return p


@pytest.fixture
def mock_session():
    """Create a mock work session within the test date range."""
    s = MagicMock(spec=WorkSession)
    s.id = 1
    s.project_id = 1
    s.session_date = date(2024, 1, 15)
    s.hours = Decimal("4.5")
    s.tasks_completed = json.dumps(["Fix login bug", "Add tests"])
    s.prs_opened = json.dumps(["https://github.com/test/test/pull/1"])
    s.notes = "Good progress"
    return s


class TestProjectUpdate:
    """Tests for ProjectUpdate dataclass."""
    
    def test_project_update_creation(self):
        """ProjectUpdate can be created."""
        update = ProjectUpdate(
            name="Test",
            hours=4.5,
            tasks=["Task 1"],
            prs=["https://github.com/pr/1"],
            notes=["Note"]
        )
        assert update.name == "Test"
        assert update.hours == 4.5


class TestClientUpdate:
    """Tests for ClientUpdate dataclass."""
    
    def test_client_update_has_activity_with_hours(self):
        """has_activity returns True when there are hours."""
        update = ClientUpdate(
            client_name="Test",
            client_email="test@example.com",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            total_hours=4.5,
            projects=[]
        )
        assert update.has_activity is True
    
    def test_client_update_has_activity_with_tasks(self):
        """has_activity returns True when there are tasks."""
        update = ClientUpdate(
            client_name="Test",
            client_email="test@example.com",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            total_hours=0,
            projects=[ProjectUpdate(
                name="Test",
                hours=0,
                tasks=["Task 1"],
                prs=[],
                notes=[]
            )]
        )
        assert update.has_activity is True
    
    def test_client_update_no_activity(self):
        """has_activity returns False when there's nothing."""
        update = ClientUpdate(
            client_name="Test",
            client_email="test@example.com",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            total_hours=0,
            projects=[]
        )
        assert update.has_activity is False


class TestGetClientUpdate:
    """Tests for get_client_update function."""
    
    @patch("src.services.update_service.get_project_with_sessions")
    @patch("src.services.update_service.list_projects")
    def test_get_client_update_with_sessions(
        self, mock_list, mock_get, mock_client, mock_project, mock_session
    ):
        """get_client_update returns summary with sessions."""
        mock_list.return_value = ([mock_project], 1)
        mock_get.return_value = (mock_project, [mock_session])
        
        update = get_client_update(
            mock_client,
            date(2024, 1, 1),
            date(2024, 1, 31)
        )
        
        assert update.client_email == "test@example.com"
        assert update.total_hours == 4.5
        assert len(update.projects) == 1
        assert update.projects[0].name == "Test Project"
        assert len(update.projects[0].tasks) == 2
    
    @patch("src.services.update_service.get_project_with_sessions")
    @patch("src.services.update_service.list_projects")
    def test_get_client_update_filters_by_date(
        self, mock_list, mock_get, mock_client, mock_project, mock_session
    ):
        """get_client_update only includes sessions in date range."""
        mock_list.return_value = ([mock_project], 1)
        mock_get.return_value = (mock_project, [mock_session])
        
        # Session is on 2024-01-15, this range excludes it
        update = get_client_update(
            mock_client,
            date(2024, 2, 1),
            date(2024, 2, 28)
        )
        
        assert update.total_hours == 0
        assert len(update.projects) == 0


class TestFormatUpdateText:
    """Tests for format_update_text function."""
    
    def test_format_with_activity(self):
        """Formats update with activity."""
        update = ClientUpdate(
            client_name="Test",
            client_email="test@example.com",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            total_hours=4.5,
            projects=[ProjectUpdate(
                name="Test Project",
                hours=4.5,
                tasks=["Fix bug"],
                prs=["https://github.com/pr/1"],
                notes=["Good progress"]
            )]
        )
        
        text = format_update_text(update)
        
        assert "Work Summary" in text
        assert "Total Hours: 4.5" in text
        assert "Test Project" in text
        assert "Fix bug" in text
        assert "https://github.com/pr/1" in text
        assert "Good progress" in text
    
    def test_format_without_activity(self):
        """Formats update without activity."""
        update = ClientUpdate(
            client_name="Test",
            client_email="test@example.com",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            total_hours=0,
            projects=[]
        )
        
        text = format_update_text(update)
        
        assert "No work sessions logged" in text


class TestSendClientUpdate:
    """Tests for send_client_update function."""
    
    @patch("src.services.email_service.send_email")
    @patch("src.services.update_service.get_client_update")
    def test_send_client_update_with_activity(
        self, mock_get_update, mock_send, mock_client
    ):
        """Sends email when there's activity."""
        mock_get_update.return_value = ClientUpdate(
            client_name="Test",
            client_email="test@example.com",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            total_hours=4.5,
            projects=[ProjectUpdate(
                name="Test",
                hours=4.5,
                tasks=["Task"],
                prs=[],
                notes=[]
            )]
        )
        mock_send.return_value = True
        
        result = send_client_update(
            mock_client,
            date(2024, 1, 1),
            date(2024, 1, 7)
        )
        
        assert result is True
        mock_send.assert_called_once()
    
    @patch("src.services.update_service.get_client_update")
    def test_send_client_update_skips_no_activity(
        self, mock_get_update, mock_client
    ):
        """Skips sending when there's no activity."""
        mock_get_update.return_value = ClientUpdate(
            client_name="Test",
            client_email="test@example.com",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            total_hours=0,
            projects=[]
        )
        
        result = send_client_update(
            mock_client,
            date(2024, 1, 1),
            date(2024, 1, 7)
        )
        
        # Returns True (not an error), but doesn't send
        assert result is True
