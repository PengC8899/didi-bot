import asyncio
import os
import pytest

from orderbot.src.core.models import OrderStatus
from orderbot.src.core.db import init_engine, get_session
from orderbot.src.services import order_service


@pytest.mark.asyncio
async def test_order_state_transitions(tmp_path, monkeypatch):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    # create order
    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="测试标题",
            content="内容",
            amount=10.5,
            created_by=1,
            created_by_username="user1",
        )

    # claim
    async with get_session() as session:
        order = await order_service.claim_order(session, order.id, 2, "op")
        assert order.status == OrderStatus.CLAIMED

    # progress -> done
    async with get_session() as session:
        order = await order_service.update_status(session, order.id, OrderStatus.IN_PROGRESS, 2)
        assert order.status == OrderStatus.IN_PROGRESS

    async with get_session() as session:
        order = await order_service.update_status(session, order.id, OrderStatus.DONE, 2)
        assert order.status == OrderStatus.DONE


@pytest.mark.asyncio
async def test_invalid_transition(tmp_path, monkeypatch):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test2.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="t",
            content="c",
            amount=None,
            created_by=1,
            created_by_username=None,
        )

    # directly to DONE should fail
    async with get_session() as session:
        with pytest.raises(order_service.BusinessError):
            await order_service.update_status(session, order.id, OrderStatus.DONE, 1)
