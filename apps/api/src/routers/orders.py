"""AstraOS Router — Orders (place, list, cancel)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..core.config import get_settings
from ..models.trading import Order, AuditLog
from ..models.user import User
from ..schemas import OrderCreate, OrderResponse

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


@router.get("/", response_model=list[OrderResponse])
async def list_orders(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all orders for the current user (BOLA: scoped)."""
    query = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(desc(Order.created_at))
        .limit(100)
    )
    if status:
        query = query.where(Order.status == status)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=OrderResponse, status_code=201)
async def place_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Place a new order — goes through risk engine first."""
    settings = get_settings()

    # Create order in DRAFT status
    order = Order(
        user_id=current_user.id,
        instrument_id=data.instrument_id,
        order_type=data.order_type,
        side=data.side,
        product=data.product,
        quantity=data.quantity,
        price=data.price,
        trigger_price=data.trigger_price,
        strategy_id=data.strategy_id,
        broker=settings.broker_provider,
        status="DRAFT",
    )
    db.add(order)
    await db.flush()

    # Risk check (imported here to avoid circular deps)
    from ..risk.risk_engine import run_risk_checks

    risk_result = await run_risk_checks(order, current_user, db)
    order.risk_checks = risk_result.checks

    if not risk_result.passed:
        order.status = "RISK_REJECTED"
        order.rejection_reason = risk_result.rejection_reason
        # Log the rejection
        db.add(AuditLog(
            user_id=current_user.id,
            action="order_risk_rejected",
            entity_type="order",
            entity_id=str(order.id),
            details={"reason": risk_result.rejection_reason, "checks": risk_result.checks},
        ))
        await db.flush()
        await db.refresh(order)
        return order

    order.status = "RISK_APPROVED"

    # Execute via broker adapter (paper for now)
    from ..broker.paper_adapter import PaperBrokerAdapter

    broker = PaperBrokerAdapter()
    broker_result = await broker.place_order(order)

    order.status = broker_result.get("status", "SENT")
    order.broker_order_id = broker_result.get("order_id")
    if broker_result.get("filled"):
        order.status = "FILLED"
        order.filled_quantity = order.quantity
        order.average_price = order.price or broker_result.get("fill_price")

    # Audit log
    db.add(AuditLog(
        user_id=current_user.id,
        action="order_placed",
        entity_type="order",
        entity_id=str(order.id),
        details={"side": data.side, "qty": data.quantity, "status": order.status},
    ))

    await db.flush()
    await db.refresh(order)
    return order


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an open order (BOLA: scoped to current user)."""
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status in ("FILLED", "CANCELLED", "REJECTED", "EXPIRED"):
        raise HTTPException(status_code=422, detail=f"Cannot cancel order in {order.status} state")

    order.status = "CANCELLED"

    db.add(AuditLog(
        user_id=current_user.id,
        action="order_cancelled",
        entity_type="order",
        entity_id=str(order.id),
        details={"previous_status": order.status},
    ))

    await db.flush()
    await db.refresh(order)
    return order
