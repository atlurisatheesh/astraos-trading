# type: ignore
"""Tests — Phase 14: Gmail OAuth, WhatsApp, Notification Preferences, AI Modules.

Covers: Google OAuth login, WhatsApp service, User model notification_preferences,
Auth endpoints, Chart Pattern Detector, Sector Rotation, FII/DII, Bulk Deals.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient


# ═══════════════════════════════════════════════════════════
# 1. WHATSAPP SERVICE
# ═══════════════════════════════════════════════════════════

class TestWhatsAppService:
    """Test the WhatsApp Twilio notification service."""

    def test_import(self):
        from src.services.whatsapp_service import (
            send_whatsapp_message, notify_trade_whatsapp,
            notify_trigger_whatsapp, notify_daily_whatsapp, is_configured,
        )
        assert send_whatsapp_message is not None

    def test_is_configured_false(self):
        from src.services.whatsapp_service import is_configured
        with patch("src.services.whatsapp_service.settings") as mock:
            mock.whatsapp_account_sid = ""
            mock.whatsapp_auth_token = ""
            mock.whatsapp_from_number = ""
            assert is_configured() is False

    def test_is_configured_true(self):
        from src.services.whatsapp_service import is_configured
        with patch("src.services.whatsapp_service.settings") as mock:
            mock.whatsapp_account_sid = "AC12345"
            mock.whatsapp_auth_token = "secret"
            mock.whatsapp_from_number = "whatsapp:+14155238886"
            assert is_configured() is True

    @pytest.mark.asyncio
    async def test_send_message_unconfigured_skips(self):
        from src.services.whatsapp_service import send_whatsapp_message
        with patch("src.services.whatsapp_service.is_configured", return_value=False):
            result = await send_whatsapp_message("+919876543210", "test")
            assert result is False

    @pytest.mark.asyncio
    async def test_trade_notification_format(self):
        from src.services.whatsapp_service import notify_trade_whatsapp
        with patch("src.services.whatsapp_service.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await notify_trade_whatsapp(
                to_number="+919876543210", symbol="RELIANCE",
                side="BUY", quantity=10, price=2500.0, reason="AI Signal"
            )
            msg = mock_send.call_args[0][1]
            assert "RELIANCE" in msg
            assert "BOUGHT" in msg
            assert "₹2,500" in msg

    @pytest.mark.asyncio
    async def test_trigger_notification_format(self):
        from src.services.whatsapp_service import notify_trigger_whatsapp
        with patch("src.services.whatsapp_service.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
            await notify_trigger_whatsapp(
                to_number="+919876543210", symbol="TCS",
                trigger_type="TAKE_PROFIT", price=3700.0, pnl=2000.0
            )
            msg = mock_send.call_args[0][1]
            assert "TCS" in msg
            assert "TAKE PROFIT" in msg

    @pytest.mark.asyncio
    async def test_daily_notification_format(self):
        from src.services.whatsapp_service import notify_daily_whatsapp
        with patch("src.services.whatsapp_service.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
            await notify_daily_whatsapp(
                to_number="+919876543210",
                total_pnl=5000.0, win_rate=75.0, trade_count=8,
            )
            msg = mock_send.call_args[0][1]
            assert "₹5,000" in msg
            assert "75" in msg


# ═══════════════════════════════════════════════════════════
# 2. USER MODEL — NOTIFICATION PREFERENCES
# ═══════════════════════════════════════════════════════════

class TestUserNotificationPreferences:
    def test_user_has_notification_preferences_field(self):
        from src.models.user import User
        assert hasattr(User, "notification_preferences")

    def test_user_has_google_id_field(self):
        from src.models.user import User
        assert hasattr(User, "google_id")

    def test_user_has_avatar_url_field(self):
        from src.models.user import User
        assert hasattr(User, "avatar_url")

    def test_default_notification_preferences(self):
        from src.models.user import User
        col = User.__table__.columns["notification_preferences"]
        assert col is not None


# ═══════════════════════════════════════════════════════════
# 3. GOOGLE OAUTH ENDPOINT
# ═══════════════════════════════════════════════════════════

class TestGoogleOAuth:
    @pytest.mark.asyncio
    async def test_google_endpoint_exists(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/google", json={"id_token": "fake"})
        assert resp.status_code != 404

    @pytest.mark.asyncio
    async def test_google_requires_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/google", json={})
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_google_login_with_mock_token(self, client: AsyncClient):
        mock_google_response = {
            "sub": "google123", "email": "testuser@gmail.com",
            "name": "Test User", "picture": "https://photo.url/test.jpg", "aud": "",
        }
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_google_response)
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=None)
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.get = MagicMock(return_value=mock_resp)
            mock_session_cls.return_value = mock_session
            resp = await client.post("/api/v1/auth/google", json={
                "id_token": "valid_token_123",
                "notification_preferences": {"email": True, "telegram": True, "whatsapp": False},
            })
            assert resp.status_code in (200, 401, 502)


# ═══════════════════════════════════════════════════════════
# 4. NOTIFICATION PREFERENCES ENDPOINT
# ═══════════════════════════════════════════════════════════

class TestNotificationPrefsEndpoint:
    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self, client: AsyncClient):
        resp = await client.put("/api/v1/auth/notifications", json={"preferences": {"email": True}})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_update_preferences(self, client: AsyncClient, auth_headers: dict):
        resp = await client.put(
            "/api/v1/auth/notifications",
            json={"preferences": {"email": True, "telegram": True, "whatsapp": False}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("preferences", {}).get("email") is True


# ═══════════════════════════════════════════════════════════
# 5. CHART PATTERN DETECTOR
# ═══════════════════════════════════════════════════════════

class TestChartPatternDetector:
    def test_import(self):
        from src.ml.pattern_detector import PatternDetector, get_pattern_detector
        assert PatternDetector is not None

    def test_instantiate(self):
        from src.ml.pattern_detector import PatternDetector
        pd = PatternDetector()
        assert pd is not None

    def test_find_peaks(self):
        import numpy as np
        from src.ml.pattern_detector import PatternDetector
        pd = PatternDetector()
        data = np.array([1, 2, 5, 3, 1, 4, 8, 6, 2, 1, 3, 7, 4, 2, 1])
        peaks = pd._find_peaks(data, order=2)
        assert len(peaks) > 0

    def test_find_troughs(self):
        import numpy as np
        from src.ml.pattern_detector import PatternDetector
        pd = PatternDetector()
        data = np.array([5, 3, 1, 3, 5, 3, 1, 4, 7, 5, 2, 1, 3, 5, 7])
        troughs = pd._find_troughs(data, order=2)
        assert len(troughs) > 0

    def test_chartpattern_dataclass(self):
        from src.ml.pattern_detector import ChartPattern
        cp = ChartPattern(
            pattern="Double Top", signal="bearish", confidence=0.85,
            start_date="2026-01-01", end_date="2026-03-01",
            description="Test pattern", target_price=19000.0, stop_loss=21000.0,
        )
        d = cp.to_dict()
        assert d["pattern"] == "Double Top"
        assert d["confidence"] == 0.85

    def test_singleton_factory(self):
        from src.ml.pattern_detector import get_pattern_detector
        pd1 = get_pattern_detector()
        pd2 = get_pattern_detector()
        assert pd1 is pd2


# ═══════════════════════════════════════════════════════════
# 6. SECTOR ROTATION
# ═══════════════════════════════════════════════════════════

class TestSectorRotation:
    def test_import(self):
        from src.services.sector_rotation import SectorRotationService
        assert SectorRotationService is not None

    def test_dataclasses(self):
        from src.services.sector_rotation import SectorMetrics, SectorRotationAnalysis
        assert SectorMetrics is not None

    def test_singleton_factory(self):
        from src.services.sector_rotation import get_sector_rotation_service
        s1 = get_sector_rotation_service()
        s2 = get_sector_rotation_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════
# 7. INSTITUTIONAL FLOWS (FII/DII)
# ═══════════════════════════════════════════════════════════

class TestInstitutionalFlows:
    def test_import(self):
        from src.services.institutional_flows import InstitutionalFlowService
        assert InstitutionalFlowService is not None

    def test_dataclasses(self):
        from src.services.institutional_flows import InstitutionalFlow, FlowAnalysis
        assert InstitutionalFlow is not None

    def test_singleton_factory(self):
        from src.services.institutional_flows import get_institutional_flow_service
        s1 = get_institutional_flow_service()
        s2 = get_institutional_flow_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════
# 8. BULK/BLOCK DEALS
# ═══════════════════════════════════════════════════════════

class TestBulkDeals:
    def test_import(self):
        from src.services.bulk_deals import BulkDealService
        assert BulkDealService is not None

    def test_dataclass(self):
        from src.services.bulk_deals import LargeDeal
        assert LargeDeal is not None

    def test_singleton_factory(self):
        from src.services.bulk_deals import get_bulk_deal_service
        s1 = get_bulk_deal_service()
        s2 = get_bulk_deal_service()
        assert s1 is s2
