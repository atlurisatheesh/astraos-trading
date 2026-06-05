# type: ignore
"""Tests — Phase 13: Email SMTP Service & Scheduled Jobs.

Covers: Email Service (templates, delivery, configuration check),
Daily/Weekly scheduled email jobs.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


# ═══════════════════════════════════════════════════════════
# 1. EMAIL SERVICE
# ═══════════════════════════════════════════════════════════

class TestEmailService:
    """Test the Email SMTP notification service."""

    def test_import(self):
        from src.services.email_service import (
            send_email,
            send_trade_alert,
            send_daily_summary,
            send_weekly_digest,
            is_configured,
        )
        assert send_email is not None

    def test_is_configured_without_creds(self):
        """Should return False when SMTP not configured."""
        from src.services.email_service import is_configured
        with patch("src.services.email_service.settings") as mock_settings:
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            mock_settings.alert_email_to = ""
            assert is_configured() is False

    def test_is_configured_with_creds(self):
        """Should return True when SMTP is configured."""
        from src.services.email_service import is_configured
        with patch("src.services.email_service.settings") as mock_settings:
            mock_settings.smtp_user = "test@gmail.com"
            mock_settings.smtp_password = "app_password"
            mock_settings.alert_email_to = "user@email.com"
            assert is_configured() is True

    @pytest.mark.asyncio
    async def test_send_email_unconfigured_skips(self):
        """Should gracefully skip delivery when not configured."""
        from src.services.email_service import send_email
        with patch("src.services.email_service.is_configured", return_value=False):
            result = await send_email("Subject", "<p>Body</p>")
            assert result is False

    @pytest.mark.asyncio
    async def test_trade_alert_html_content(self):
        """Trade alert should generate valid HTML."""
        from src.services.email_service import send_trade_alert
        with patch("src.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            result = await send_trade_alert(
                symbol="RELIANCE", side="BUY", quantity=10,
                price=2500.0, reason="AI Signal"
            )
            assert result is True
            # Verify HTML content was generated
            call_args = mock_send.call_args
            subject = call_args[0][0]
            html = call_args[0][1]
            assert "RELIANCE" in subject
            assert "BOUGHT" in html or "BUY" in html
            assert "₹2,500" in html

    @pytest.mark.asyncio
    async def test_sell_alert_html_content(self):
        """Sell alert should show red styling."""
        from src.services.email_service import send_trade_alert
        with patch("src.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await send_trade_alert(
                symbol="TCS", side="SELL", quantity=5,
                price=3500.0, reason="Stop Loss Hit"
            )
            html = mock_send.call_args[0][1]
            assert "SOLD" in html or "SELL" in html
            assert "ef4444" in html  # Red color

    @pytest.mark.asyncio
    async def test_daily_summary_html(self):
        """Daily summary should include P&L, trades, and win rate."""
        from src.services.email_service import send_daily_summary
        with patch("src.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            positions = [
                {"symbol": "RELIANCE", "pnl": 5000},
                {"symbol": "TCS", "pnl": -2000},
            ]
            await send_daily_summary(
                total_pnl=3000.0, win_rate=66.7,
                trade_count=2, positions=positions
            )
            html = mock_send.call_args[0][1]
            assert "₹3,000" in html
            assert "Daily" in mock_send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_weekly_digest_html(self):
        """Weekly digest should include weekly P&L and best/worst trades."""
        from src.services.email_service import send_weekly_digest
        with patch("src.services.email_service.send_email", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await send_weekly_digest(
                weekly_pnl=15000.0,
                best_trade={"symbol": "RELIANCE", "pnl": 8000},
                worst_trade={"symbol": "ITC", "pnl": -1500},
                total_trades=12,
            )
            html = mock_send.call_args[0][1]
            assert "₹15,000" in html
            assert "RELIANCE" in html
            assert "Weekly" in mock_send.call_args[0][0]


# ═══════════════════════════════════════════════════════════
# 2. SCHEDULED EMAIL JOBS
# ═══════════════════════════════════════════════════════════

class TestScheduledJobs:
    """Test the scheduled daily/weekly email jobs."""

    def test_daily_job_import(self):
        from src.scheduler.jobs import job_daily_email_report
        assert job_daily_email_report is not None

    def test_weekly_job_import(self):
        from src.scheduler.jobs import job_weekly_digest
        assert job_weekly_digest is not None

    @pytest.mark.asyncio
    async def test_daily_job_skips_if_unconfigured(self):
        """Daily email job should skip when SMTP not configured."""
        with patch("src.services.email_service.is_configured", return_value=False):
            from src.scheduler.jobs import job_daily_email_report
            # Should not raise
            await job_daily_email_report()

    @pytest.mark.asyncio
    async def test_weekly_job_skips_if_unconfigured(self):
        """Weekly digest job should skip when SMTP not configured."""
        with patch("src.services.email_service.is_configured", return_value=False):
            from src.scheduler.jobs import job_weekly_digest
            # Should not raise
            await job_weekly_digest()
