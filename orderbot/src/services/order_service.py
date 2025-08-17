from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.models import OrderStatus, Order, ApplicationStatus
from ..core import repo
from ..utils.logging import log_info, log_error
from .channel_publisher import publish_order_to_channel, edit_order_message


class BusinessError(Exception):
    """Domain/business errors for invalid transitions or permissions."""


def _check_transition(old: OrderStatus, new: OrderStatus) -> None:
    allowed = {
        OrderStatus.DRAFT: {OrderStatus.NEW, OrderStatus.CANCELED},
        OrderStatus.NEW: {OrderStatus.CLAIMED, OrderStatus.CANCELED},
        OrderStatus.CLAIMED: {OrderStatus.IN_PROGRESS, OrderStatus.CANCELED},
        OrderStatus.IN_PROGRESS: {OrderStatus.DONE, OrderStatus.CANCELED},
        OrderStatus.DONE: set(),
        OrderStatus.CANCELED: set(),
    }
    if new not in allowed[old]:
        raise BusinessError(f"invalid_transition: {old} -> {new}")


async def create_order(
    session: AsyncSession,
    *,
    title: str,
    content: str,
    amount: Optional[float],
    created_by: int,
    created_by_username: Optional[str],
    image_path: Optional[str] = None,
) -> Order:
    order = await repo.create_order(
        session,
        title=title,
        content=content,
        amount=amount,
        created_by=created_by,
        created_by_username=created_by_username,
        image_path=image_path,
    )
    # publish to channel (idempotent)
    try:
        message_id = await publish_order_to_channel(order)
        await repo.update_order_fields(session, order.id, channel_message_id=message_id)
    except Exception as e:  # noqa: BLE001
        log_error("channel.publish.failed", order_id=order.id, error=str(e))
    return order


async def create_order_draft(
    session: AsyncSession,
    *,
    title: str,
    content: str,
    amount: Optional[float],
    created_by: int,
    created_by_username: Optional[str],
    contact_username: Optional[str] = None,
) -> Order:
    """仅创建订单草稿，不发布频道消息。"""
    order = await repo.create_order(
        session,
        title=title,
        content=content,
        amount=amount,
        created_by=created_by,
        created_by_username=created_by_username,
        contact_username=contact_username,
        status=OrderStatus.DRAFT,
    )
    return order


async def publish_draft(session: AsyncSession, order_id: int) -> Order:
    """将草稿发布到频道（若尚未发布），并回写 channel_message_id。"""
    order = await repo.get_order_by_id(session, order_id)
    if not order:
        raise BusinessError("order_not_found")
    
    # 检查状态转换
    if order.status == OrderStatus.DRAFT:
        _check_transition(order.status, OrderStatus.NEW)
        # 更新状态为NEW
        updated = await repo.update_order_fields(session, order_id, status=OrderStatus.NEW)
        if updated is None:
            raise BusinessError("update_failed")
        # 记录状态变更历史
        await repo.add_history(session, order_id, from_status=order.status, to_status=OrderStatus.NEW, actor_user_id=order.created_by)
        order = updated
    
    try:
        message_id = await publish_order_to_channel(order)
        if message_id is not None:
            updated = await repo.update_order_fields(session, order_id, channel_message_id=message_id)
            if updated is None:
                raise BusinessError("update_failed")
            return updated
        # 未配置频道/Token的情况下，仍返回当前对象
        return order
    except Exception as e:  # noqa: BLE001
        log_error("channel.publish.failed", order_id=order_id, error=str(e))
        return order

async def claim_order(session: AsyncSession, order_id: int, actor_tg_user_id: int, actor_username: Optional[str]) -> Order:
    order = await repo.get_order_by_id_for_update(session, order_id)
    if not order:
        raise BusinessError("order_not_found")
    if order.status != OrderStatus.NEW:
        raise BusinessError("only_NEW_can_be_claimed")

    from_status = order.status
    updated_order = await repo.update_order_fields(
        session,
        order_id,
        status=OrderStatus.CLAIMED,
        claimed_by=actor_tg_user_id,
        claimed_by_username=actor_username,
    )
    if updated_order is None:
        raise BusinessError("update_failed")
    await repo.add_history(session, order_id, from_status=from_status, to_status=OrderStatus.CLAIMED, actor_user_id=actor_tg_user_id)

    # edit channel message
    try:
        await edit_order_message(updated_order)
    except Exception as e:  # noqa: BLE001
        log_error("channel.edit.failed", order_id=updated_order.id, error=str(e))
    return updated_order


async def update_status(
    session: AsyncSession,
    order_id: int,
    new_status: OrderStatus,
    actor_tg_user_id: int,
    note: Optional[str] = None,
) -> Order:
    order = await repo.get_order_by_id_for_update(session, order_id)
    if not order:
        raise BusinessError("order_not_found")

    # validate state machine
    if order.status == new_status:
        return order
    _check_transition(OrderStatus(order.status), new_status)

    from_status = order.status
    updated_order = await repo.update_order_fields(session, order_id, status=new_status)
    if updated_order is None:
        raise BusinessError("update_failed")
    await repo.add_history(session, order_id, from_status=OrderStatus(from_status), to_status=new_status, actor_user_id=actor_tg_user_id, note=note)

    try:
        await edit_order_message(updated_order)
    except Exception as e:  # noqa: BLE001
        log_error("channel.edit.failed", order_id=updated_order.id, error=str(e))
    return updated_order


async def get_user_related_orders(session: AsyncSession, tg_user_id: int) -> list[Order]:
    return list(await repo.get_user_related_orders(session, tg_user_id))


async def get_orders_by_user(session: AsyncSession, user_id: int) -> list[Order]:
    """获取用户相关的订单"""
    return list(await repo.get_user_related_orders(session, user_id))


async def get_orders_by_user_and_date_range(session: AsyncSession, user_id: int, start_date, end_date) -> list[Order]:
    """获取用户在指定日期范围内的订单"""
    from sqlalchemy import select, and_
    from datetime import datetime
    
    # 确保日期是datetime对象
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date)
    
    result = await session.execute(
        select(Order).where(
            and_(
                (Order.created_by == user_id) | (Order.claimed_by == user_id),
                Order.created_at >= start_date,
                Order.created_at <= end_date
            )
        ).order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


# ---- Applications and review ----
async def apply_for_order(session: AsyncSession, order_id: int, *, applicant_tg_id: int, applicant_username: Optional[str]) -> None:
    order = await repo.get_order_by_id(session, order_id)
    if not order:
        raise BusinessError("order_not_found")
    # anyone can apply (可按配置限制)，仅写 application，不改订单状态
    await repo.create_or_get_application(
        session,
        order_id=order_id,
        applicant_tg_id=applicant_tg_id,
        applicant_username=applicant_username,
    )


async def approve_application(
    session: AsyncSession,
    *,
    order_id: int,
    app_id: int,
    approver_tg_id: int,
) -> Order:
    order = await repo.get_order_by_id_for_update(session, order_id)
    if not order:
        raise BusinessError("order_not_found")
    # 审核通过：订单 NEW -> CLAIMED，并设置 claimed_by
    if order.status != OrderStatus.NEW:
        raise BusinessError("only_NEW_can_be_claimed")
    # 标记 application = APPROVED，并将该申请者认领为执行人
    app = await repo.get_application_by_id(session, app_id)
    if not app:
        raise BusinessError("application_not_found")
    await repo.update_application_status(session, app_id, ApplicationStatus.APPROVED)
    # 认领为申请人
    updated = await repo.update_order_fields(
        session,
        order_id,
        status=OrderStatus.CLAIMED,
        claimed_by=app.applicant_tg_id,
        claimed_by_username=app.applicant_username,
    )
    await repo.add_history(session, order_id, from_status=order.status, to_status=OrderStatus.CLAIMED, actor_user_id=approver_tg_id)
    try:
        await edit_order_message(updated)  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001
        log_error("channel.edit.failed", order_id=order_id, error=str(e))
    # updated 类型是 Optional[Order]（来自 repo），此处确保不为 None
    if updated is None:
        raise BusinessError("update_failed")
    return updated


async def reject_application(session: AsyncSession, *, app_id: int, reviewer_tg_id: int) -> None:
    await repo.update_application_status(session, app_id, ApplicationStatus.REJECTED)


async def delete_order(session: AsyncSession, order_id: int, actor_tg_user_id: int) -> None:
    """删除订单"""
    order = await repo.get_order_by_id(session, order_id)
    if not order:
        raise BusinessError("order_not_found")
    
    # 删除订单记录
    await repo.delete_order(session, order_id)
    log_info("order.deleted", order_id=order_id, actor_tg_user_id=actor_tg_user_id)
