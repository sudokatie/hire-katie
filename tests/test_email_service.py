"""Tests for email service."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.services.email_service import (
    render_template,
    send_email,
    parse_envelope_list,
    Email,
)


class TestRenderTemplate:
    def test_extracts_subject(self, tmp_path):
        template = tmp_path / "test.txt"
        template.write_text("Subject: Hello {name}\n\nBody here")
        
        subject, body = render_template("test", {"name": "World"}, str(tmp_path))
        
        assert subject == "Hello World"
        assert "Body here" in body

    def test_replaces_variables(self, tmp_path):
        template = tmp_path / "vars.txt"
        template.write_text("Subject: Test\n\nHello {name}, your project is {project}.")
        
        subject, body = render_template(
            "vars",
            {"name": "Alice", "project": "Awesome"},
            str(tmp_path)
        )
        
        assert "Hello Alice" in body
        assert "Awesome" in body

    def test_raises_for_missing_template(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            render_template("missing", {}, str(tmp_path))


class TestSendEmail:
    def test_constructs_mml(self, mock_subprocess):
        result = send_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        assert result is True
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        assert 'himalaya' in call_args[0][0]

    def test_returns_false_on_failure(self, mock_subprocess):
        mock_subprocess.return_value = MagicMock(returncode=1, stderr="Error")
        
        result = send_email(
            to="test@example.com",
            subject="Test",
            body="Body"
        )
        
        assert result is False

    def test_returns_false_on_timeout(self, mock_subprocess):
        import subprocess
        mock_subprocess.side_effect = subprocess.TimeoutExpired('cmd', 30)
        
        result = send_email(
            to="test@example.com",
            subject="Test",
            body="Body"
        )
        
        assert result is False


class TestParseEnvelopeList:
    def test_parses_standard_output(self):
        output = """*1  2024-01-26  sender@example.com  Subject Line
2  2024-01-25  other@example.com  Another Subject"""
        
        emails = parse_envelope_list(output)
        
        assert len(emails) == 2
        assert emails[0].id == "1"
        assert emails[0].is_unread is True
        assert emails[0].from_addr == "sender@example.com"
        assert emails[1].is_unread is False

    def test_handles_empty_output(self):
        emails = parse_envelope_list("")
        assert emails == []

    def test_handles_header_lines(self):
        output = """ID  DATE  FROM  SUBJECT
---  ----  ----  -------
*1  2024-01-26  test@example.com  Test"""
        
        emails = parse_envelope_list(output)
        # Should only parse the actual email line
        assert len(emails) <= 1
