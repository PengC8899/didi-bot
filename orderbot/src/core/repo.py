from __future__ import annotations

from typing import Optional, Sequence
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Order, OrderStatus, OrderStatusHistory, OrderApplication, ApplicationStatus


async def get_order_by_id(session: AsyncSession, order_id: int) -> Optional[Order]:
    result = await session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def get_order_by_id_for_update(session: AsyncSession, order_id: int) -> Optional[Order]:
    # Placeholder for Postgres FOR UPDATE support in future
    result = await session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def create_order(
    session: AsyncSession,
    *,
    title: str,
    content: str,
    amount: Optional[float],
    created_by: int,
    created_by_username: Optional[str],
    contact_username: Optional[str] = None,
    image_path: Optional[str] = None,
    status: OrderStatus = OrderStatus.NEW,
) -> Order:
    order = Order(
        title=title,
        content=content,
        amount=amount,
        status=status,
        created_by=created_by,
        created_by_username=created_by_username,
        contact_username=contact_username,
        image_path=image_path,
    )
    session.add(order)
    await session.flush()

    history = OrderStatusHistory(order_id=order.id, from_status=None, to_status=status, actor_user_id=created_by)
    session.add(history)
    return order


async def update_order_fields(session: AsyncSession, order_id: int, **fields) -> Optional[Order]:
    await session.execute(update(Order).where(Order.id == order_id).values(**fields))
    # re-fetch updated row
    return await get_order_by_id(session, order_id)


async def add_history(
    session: AsyncSession,
    order_id: int,
    *,
    from_status: Optional[OrderStatus],
    to_status: OrderStatus,
    actor_user_id: int,
    note: Optional[str] = None,
) -> OrderStatusHistory:
    hist = OrderStatusHistory(order_id=order_id, from_status=from_status, to_status=to_status, actor_user_id=actor_user_id, note=note)
    session.add(hist)
    await session.flush()
    return hist


async def get_user_related_orders(session: AsyncSession, tg_user_id: int) -> Sequence[Order]:
    result = await session.execute(
        select(Order).where(
            (Order.created_by == tg_user_id) | (Order.claimed_by == tg_user_id)
        ).order_by(Order.updated_at.desc()).limit(20)
    )
    return result.scalars().all()


# ---- Applications ----
async def get_application(session: AsyncSession, order_id: int, applicant_tg_id: int) -> Optional[OrderApplication]:
    result = await session.execute(
        select(OrderApplication).where(and_(OrderApplication.order_id == order_id, OrderApplication.applicant_tg_id == applicant_tg_id))
    )
    return result.scalar_one_or_none()


async def create_or_get_application(
    session: AsyncSession,
    *,
    order_id: int,
    applicant_tg_id: int,
    applicant_username: Optional[str],
) -> OrderApplication:
    app = await get_application(session, order_id, applicant_tg_id)
    if app:
        return app
    app = OrderApplication(order_id=order_id, applicant_tg_id=applicant_tg_id, applicant_username=applicant_username)
    session.add(app)
    await session.flush()
    return app


async def list_applications_for_order(session: AsyncSession, order_id: int, *, status: Optional[ApplicationStatus] = None) -> Sequence[OrderApplication]:
    stmt = select(OrderApplication).where(OrderApplication.order_id == order_id).order_by(OrderApplication.created_at.asc())
    if status is not None:
        stmt = stmt.where(OrderApplication.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_application_status(session: AsyncSession, app_id: int, status: ApplicationStatus) -> Optional[OrderApplication]:
    await session.execute(update(OrderApplication).where(OrderApplication.id == app_id).values(status=status))
    result = await session.execute(select(OrderApplication).where(OrderApplication.id == app_id))
    return result.scalar_one_or_none()


async def get_application_by_id(session: AsyncSession, app_id: int) -> Optional[OrderApplication]:
    result = await session.execute(select(OrderApplication).where(OrderApplication.id == app_id))
    return result.scalar_one_or_none()


async def delete_order(session: AsyncSession, order_id: int) -> None:
    """删除订单及其相关记录"""
    # 删除相关的申请记录
    await session.execute(update(OrderApplication).where(OrderApplication.order_id == order_id).values(status=ApplicationStatus.REJECTED))
    # 删除订单记录
    from sqlalchemy import delete
    await session.execute(delete(Order).where(Order.id == order_id))
