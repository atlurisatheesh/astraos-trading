"""AstraOS Tests — Risk Engine (the most critical tests)."""

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.instrument import Instrument
from src.models.trading import Order, Position, Strategy
from src.risk.risk_engine import run_risk_checks
from src.risk.kill_switch import strategy_kill, account_kill
from src.core.security import hash_password


@pytest.mark.asyncio
class TestRiskEngine:
    """Risk engine tests — verify every hard limit is enforced."""

    @pytest_asyncio.fixture
    async def rich_user(self, db_session: AsyncSession) -> User:
        """User with 10L capital."""
        user = User(
            id=uuid.uuid4(),
            email="rich@astraos.dev",
            password_hash=hash_password("TestPass123456"),
            full_name="Rich User",
            risk_profile={"capital": 1000000},  # 10 lakh
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest_asyncio.fixture
    async def instrument(self, db_session: AsyncSession) -> Instrument:
        instrument = Instrument(
            symbol="INFY",
            exchange="NSE",
            instrument_type="EQ",
            name="Infosys Ltd",
            lot_size=1,
        )
        db_session.add(instrument)
        await db_session.commit()
        await db_session.refresh(instrument)
        return instrument

    async def test_small_order_passes(self, db_session, rich_user, instrument):
        """A small order within all limits should pass."""
        order = Order(
            id=uuid.uuid4(),
            user_id=rich_user.id,
            instrument_id=instrument.id,
            order_type="MARKET",
            side="BUY",
            product="CNC",
            quantity=10,
            price=Decimal("1500.00"),
            broker="paper",
            status="DRAFT",
        )
        db_session.add(order)
        await db_session.flush()

        result = await run_risk_checks(order, rich_user, db_session)
        assert result.passed is True
        assert all(result.checks.values())

    async def test_oversized_position_rejected(self, db_session, rich_user, instrument):
        """Order exceeding 5% of capital should be rejected."""
        # 10L capital, 5% = 50K max. This order = 100 * 1500 = 1.5L > 50K
        order = Order(
            id=uuid.uuid4(),
            user_id=rich_user.id,
            instrument_id=instrument.id,
            order_type="LIMIT",
            side="BUY",
            product="CNC",
            quantity=100,
            price=Decimal("1500.00"),
            broker="paper",
            status="DRAFT",
        )
        db_session.add(order)
        await db_session.flush()

        result = await run_risk_checks(order, rich_user, db_session)
        assert result.passed is False
        assert result.checks["position_size"] is False
        assert "Position too large" in result.rejection_reason

    async def test_leverage_limit_enforced(self, db_session, rich_user, instrument):
        """Leverage exceeding 2x capital should be rejected."""
        # Capital = 10L, max leverage = 2x = 20L
        # Create existing positions totaling 19.5L
        for i in range(20):
            pos = Position(
                id=uuid.uuid4(),
                user_id=rich_user.id,
                instrument_id=instrument.id,
                side="LONG",
                quantity=100,
                average_cost=Decimal("975.00"),  # 20 * 100 * 975 = 19.5L
                is_open=True,
            )
            db_session.add(pos)
        await db_session.flush()

        # New order = 100 * 1500 = 1.5L -> total = 21L > 20L (2x leverage)
        order = Order(
            id=uuid.uuid4(),
            user_id=rich_user.id,
            instrument_id=instrument.id,
            order_type="MARKET",
            side="BUY",
            product="CNC",
            quantity=100,
            price=Decimal("1500.00"),
            broker="paper",
            status="DRAFT",
        )
        db_session.add(order)
        await db_session.flush()

        result = await run_risk_checks(order, rich_user, db_session)
        assert result.passed is False
        assert result.checks["leverage"] is False

    async def test_cash_reserve_enforced(self, db_session, rich_user, instrument):
        """Must maintain 20% cash reserve."""
        # Create positions using 85% of capital (850K)
        for i in range(17):
            pos = Position(
                id=uuid.uuid4(),
                user_id=rich_user.id,
                instrument_id=instrument.id,
                side="LONG",
                quantity=50,
                average_cost=Decimal("1000.00"),
                is_open=True,
            )
            db_session.add(pos)
        await db_session.flush()

        # This would leave < 20% cash
        order = Order(
            id=uuid.uuid4(),
            user_id=rich_user.id,
            instrument_id=instrument.id,
            order_type="MARKET",
            side="BUY",
            product="CNC",
            quantity=10,
            price=Decimal("1500.00"),
            broker="paper",
            status="DRAFT",
        )
        db_session.add(order)
        await db_session.flush()

        result = await run_risk_checks(order, rich_user, db_session)
        assert result.passed is False
        assert result.checks["cash_reserve"] is False


@pytest.mark.asyncio
class TestKillSwitch:
    """Kill switch tests — verify positions close and strategies halt."""

    @pytest_asyncio.fixture
    async def setup_trading(self, db_session: AsyncSession):
        user = User(
            id=uuid.uuid4(),
            email="killtest@astraos.dev",
            password_hash=hash_password("TestPass123456"),
            full_name="Kill Test",
        )
        db_session.add(user)

        instrument = Instrument(
            symbol="TCS", exchange="NSE", instrument_type="EQ", name="TCS Ltd", lot_size=1,
        )
        db_session.add(instrument)
        await db_session.flush()

        strategy = Strategy(
            id=uuid.uuid4(),
            user_id=user.id,
            name="Test Momentum",
            strategy_type="momentum",
            asset_class="equity",
            timeframe="swing",
            is_active=True,
        )
        db_session.add(strategy)

        position = Position(
            id=uuid.uuid4(),
            user_id=user.id,
            instrument_id=instrument.id,
            strategy_id=strategy.id,
            side="LONG",
            quantity=50,
            average_cost=Decimal("3500.00"),
            is_open=True,
        )
        db_session.add(position)

        order = Order(
            id=uuid.uuid4(),
            user_id=user.id,
            instrument_id=instrument.id,
            strategy_id=strategy.id,
            order_type="LIMIT",
            side="BUY",
            product="CNC",
            quantity=20,
            price=Decimal("3400.00"),
            broker="paper",
            status="SENT",
        )
        db_session.add(order)
        await db_session.commit()

        return {"user": user, "strategy": strategy, "position": position, "order": order}

    async def test_strategy_kill(self, db_session, setup_trading):
        """L1 kill: strategy disabled, orders cancelled."""
        data = setup_trading
        result = await strategy_kill(
            str(data["strategy"].id), data["user"].id, db_session,
        )
        await db_session.commit()

        assert result["level"] == 1
        assert result["action"] == "strategy_killed"

    async def test_account_kill(self, db_session, setup_trading):
        """L2 kill: all positions closed, all strategies halted."""
        data = setup_trading
        result = await account_kill(data["user"].id, db_session)
        await db_session.commit()

        assert result["level"] == 2
        assert result["action"] == "account_killed"
