"""Tests for CLI module."""

import pytest
from unittest.mock import patch, MagicMock

from src.cli import main, cmd_send_updates


class TestSendUpdatesCommand:
    """Tests for send-updates command."""
    
    @patch("src.cli.send_weekly_updates")
    @patch("src.cli.init_db")
    def test_weekly_updates_success(self, mock_init, mock_send):
        """Weekly updates command returns 0 on success."""
        mock_send.return_value = (5, 0)  # 5 sent, 0 failed
        
        args = MagicMock()
        args.period = "weekly"
        
        result = cmd_send_updates(args)
        
        assert result == 0
        mock_send.assert_called_once()
    
    @patch("src.cli.send_monthly_updates")
    @patch("src.cli.init_db")
    def test_monthly_updates_success(self, mock_init, mock_send):
        """Monthly updates command returns 0 on success."""
        mock_send.return_value = (3, 0)  # 3 sent, 0 failed
        
        args = MagicMock()
        args.period = "monthly"
        
        result = cmd_send_updates(args)
        
        assert result == 0
        mock_send.assert_called_once()
    
    @patch("src.cli.send_weekly_updates")
    @patch("src.cli.init_db")
    def test_returns_1_on_failures(self, mock_init, mock_send):
        """Command returns 1 if any emails failed."""
        mock_send.return_value = (4, 1)  # 4 sent, 1 failed
        
        args = MagicMock()
        args.period = "weekly"
        
        result = cmd_send_updates(args)
        
        assert result == 1
    
    @patch("src.cli.init_db")
    def test_unknown_period_returns_1(self, mock_init):
        """Unknown period returns 1."""
        args = MagicMock()
        args.period = "daily"  # Not a valid period
        
        result = cmd_send_updates(args)
        
        assert result == 1


class TestMainEntrypoint:
    """Tests for main CLI entrypoint."""
    
    def test_no_command_returns_1(self):
        """No command prints help and returns 1."""
        with patch("sys.argv", ["hire-katie"]):
            result = main()
            assert result == 1
    
    @patch("src.cli.send_weekly_updates")
    @patch("src.cli.init_db")
    def test_send_updates_weekly(self, mock_init, mock_send):
        """send-updates weekly command works."""
        mock_send.return_value = (2, 0)
        
        with patch("sys.argv", ["hire-katie", "send-updates", "weekly"]):
            result = main()
        
        assert result == 0
        mock_send.assert_called_once()
