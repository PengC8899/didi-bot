import os
import pytest

from ..core.db import init_engine, get_session
from ..services import order_service


@pytest.mark.asyncio
async def test_create_and_get_orders(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test3.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    # create two orders by same user
    async with get_session() as session:
        o1 = await order_service.create_order(session, title="A", content="a", amount=None, created_by=111, created_by_username="a1")
        o2 = await order_service.create_order(session, title="B", content="b", amount=20.0, created_by=111, created_by_username="a1")

    # claim one by other user
    async with get_session() as session:
        await order_service.claim_order(session, o1.id, 222, "op222")

    # fetch related
    async with get_session() as session:
        mine = await order_service.get_user_related_orders(session, 111)
        theirs = await order_service.get_user_related_orders(session, 222)

    assert len(mine) == 2
    assert len(theirs) == 1
