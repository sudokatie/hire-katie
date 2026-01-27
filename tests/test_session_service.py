"""Tests for session service."""

from datetime import date
from decimal import Decimal

import pytest

from src.services import (
    get_monthly_summary,
    get_sessions_for_project,
    get_total_hours,
    log_session,
    parse_session_json,
)


class TestLogSession:
    """Tests for log_session."""

    def test_creates_session(self, sample_project, db_session):
        """Should create a work session."""
        session = log_session(
            project_id=sample_project.id,
            session_date=date(2026, 1, 15),
            hours=Decimal("4.5")
        )
        
        assert session.id is not None
        assert session.project_id == sample_project.id
        assert session.session_date == date(2026, 1, 15)
        assert session.hours == Decimal("4.5")

    def test_creates_with_all_fields(self, sample_project, db_session):
        """Should create session with tasks, PRs, and notes."""
        session = log_session(
            project_id=sample_project.id,
            session_date=date(2026, 1, 15),
            hours=Decimal("8"),
            tasks_completed=["Fixed bug", "Added feature"],
            prs_opened=["https://github.com/test/pr/1"],
            notes="Good progress today"
        )
        
        assert session.id is not None
        assert "Fixed bug" in session.tasks_completed
        assert "https://github.com/test/pr/1" in session.prs_opened
        assert session.notes == "Good progress today"

    def test_raises_for_missing_project(self, db_session):
        """Should raise ValueError for nonexistent project."""
        with pytest.raises(ValueError, match="not found"):
            log_session(
                project_id=99999,
                session_date=date(2026, 1, 15),
                hours=Decimal("4")
            )


class TestGetSessionsForProject:
    """Tests for get_sessions_for_project."""

    def test_returns_sessions(self, sample_project, db_session):
        """Should return all sessions for a project."""
        log_session(sample_project.id, date(2026, 1, 10), Decimal("4"))
        log_session(sample_project.id, date(2026, 1, 15), Decimal("8"))
        
        sessions = get_sessions_for_project(sample_project.id)
        
        assert len(sessions) == 2
        # Should be ordered by date descending
        assert sessions[0].session_date == date(2026, 1, 15)
        assert sessions[1].session_date == date(2026, 1, 10)

    def test_returns_empty_for_no_sessions(self, sample_project, db_session):
        """Should return empty list if no sessions."""
        sessions = get_sessions_for_project(sample_project.id)
        assert sessions == []


class TestGetTotalHours:
    """Tests for get_total_hours."""

    def test_returns_total(self, sample_project, db_session):
        """Should sum all hours for a project."""
        log_session(sample_project.id, date(2026, 1, 10), Decimal("4.5"))
        log_session(sample_project.id, date(2026, 1, 15), Decimal("3.5"))
        
        total = get_total_hours(sample_project.id)
        
        assert total == Decimal("8.0")

    def test_returns_zero_for_no_sessions(self, sample_project, db_session):
        """Should return 0 if no sessions."""
        total = get_total_hours(sample_project.id)
        assert total == Decimal("0")


class TestGetMonthlySummary:
    """Tests for get_monthly_summary."""

    def test_returns_summary(self, sample_project, db_session):
        """Should return summary for a specific month."""
        log_session(
            sample_project.id,
            date(2026, 1, 15),
            Decimal("8"),
            tasks_completed=["Task 1", "Task 2"],
            prs_opened=["https://github.com/pr/1"]
        )
        
        summary = get_monthly_summary(sample_project.id, 2026, 1)
        
        assert summary["year"] == 2026
        assert summary["month"] == 1
        assert summary["sessions"] == 1
        assert summary["total_hours"] == 8.0
        assert "Task 1" in summary["tasks_completed"]
        assert "https://github.com/pr/1" in summary["prs_opened"]

    def test_returns_empty_for_different_month(self, sample_project, db_session):
        """Should return empty summary for month with no sessions."""
        log_session(sample_project.id, date(2026, 1, 15), Decimal("8"))
        
        summary = get_monthly_summary(sample_project.id, 2026, 2)
        
        assert summary["sessions"] == 0
        assert summary["total_hours"] == 0.0


class TestParseSessionJson:
    """Tests for parse_session_json."""

    def test_parses_session(self, sample_project, db_session):
        """Should convert session to dict with parsed JSON."""
        session = log_session(
            sample_project.id,
            date(2026, 1, 15),
            Decimal("4"),
            tasks_completed=["Task 1"],
            prs_opened=["https://github.com/pr/1"],
            notes="Test notes"
        )
        
        result = parse_session_json(session)
        
        assert result["id"] == session.id
        assert result["session_date"] == "2026-01-15"
        assert result["hours"] == 4.0
        assert result["tasks_completed"] == ["Task 1"]
        assert result["prs_opened"] == ["https://github.com/pr/1"]
        assert result["notes"] == "Test notes"
