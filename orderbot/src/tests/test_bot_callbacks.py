import os
import pytest

from ..core.db import init_engine, get_session
from ..services import order_service
from ..core.models import OrderStatus
from ..tg.bot import cb_claim, cb_progress, cb_done, cb_cancel, cb_publish_order, cb_delete_order


class DummyFromUser:
    def __init__(self, user_id: int, username: str | None = None):
        self.id = user_id
        self.username = username


class DummyCallback:
    def __init__(self, data: str, user_id: int = 1, username: str | None = "u"):
        self.data = data
        self.from_user = DummyFromUser(user_id, username)
        self.answered: list[tuple[str, bool]] = []

    async def answer(self, text: str, show_alert: bool = False):
        self.answered.append((text, show_alert))


@pytest.mark.asyncio
async def test_cb_claim_only_new_can_be_claimed(tmp_path, monkeypatch):
    # ensure channel publisher is skipped
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)

    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb1.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    # create a new order
    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="T",
            content="C",
            amount=None,
            created_by=10,
            created_by_username="u10",
        )
        await session.commit()

    # first claim to move it out of NEW
    async with get_session() as session:
        await order_service.claim_order(session, order.id, actor_tg_user_id=20, actor_username="op")
        await session.commit()

    # second claim via callback should raise business error and answer alert
    cq = DummyCallback(data=f"claim:{order.id}", user_id=30, username="u30")
    await cb_claim(cq)  # type: ignore[arg-type]

    assert cq.answered, "callback should have answered with an alert"
    msg, alert = cq.answered[-1]
    assert "only_NEW_can_be_claimed" in msg
    assert alert is True


@pytest.mark.asyncio
async def test_cb_progress_invalid_transition(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)

    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb2.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    # create NEW order
    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="P",
            content="C",
            amount=None,
            created_by=1,
            created_by_username="u1",
        )
        await session.commit()

    # progress from NEW is invalid -> should alert with invalid_transition
    cq = DummyCallback(data=f"progress:{order.id}", user_id=1, username="u1")
    await cb_progress(cq)  # type: ignore[arg-type]

    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "invalid_transition" in msg
    assert alert is True


@pytest.mark.asyncio
async def test_cb_done_order_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)

    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb3.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    cq = DummyCallback(data="done:999999", user_id=1, username="u1")
    await cb_done(cq)  # type: ignore[arg-type]

    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "order_not_found" in msg
    assert alert is True


@pytest.mark.asyncio
async def test_cb_cancel_success(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)

    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb4.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    # create NEW order
    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="X",
            content="Y",
            amount=None,
            created_by=1,
            created_by_username="u1",
        )
        await session.commit()

    cq = DummyCallback(data=f"cancel:{order.id}", user_id=1, username="u1")
    await cb_cancel(cq)  # type: ignore[arg-type]

    # success message, no alert
    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "已取消" in msg
    assert alert is False


@pytest.mark.asyncio
async def test_cb_publish_order_no_channel_config(tmp_path, monkeypatch):
    # disable channel publisher to test no config scenario
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb_publish.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    # create NEW order
    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="Test Publish Order",
            content="Test content for publishing",
            amount=100,
            created_by=1,
            created_by_username="testuser",
        )
        await session.commit()
    
    cq = DummyCallback(data=f"publish:{order.id}", user_id=1, username="testuser")
    await cb_publish_order(cq)  # type: ignore[arg-type]
    
    # should answer with channel config incomplete message
    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "频道配置不完整" in msg
    assert alert is True


@pytest.mark.asyncio
async def test_cb_publish_order_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb_publish_nf.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    cq = DummyCallback(data="publish:999999", user_id=1, username="testuser")
    await cb_publish_order(cq)  # type: ignore[arg-type]
    
    # should answer with error alert
    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "订单不存在" in msg
    assert alert is True


@pytest.mark.asyncio
async def test_cb_delete_order_success(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb_delete.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    # create NEW order
    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="Test Delete Order",
            content="Test content for deletion",
            amount=200,
            created_by=1,
            created_by_username="testuser",
        )
        await session.commit()
    
    cq = DummyCallback(data=f"delete:{order.id}", user_id=1, username="testuser")
    await cb_delete_order(cq)  # type: ignore[arg-type]
    
    # should answer with success message
    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "已成功删除" in msg
    assert alert is True
    
    # verify order is actually deleted
    async with get_session() as session:
        from orderbot.src.core import repo
        deleted_order = await repo.get_order_by_id(session, order.id)
        assert deleted_order is None


@pytest.mark.asyncio
async def test_cb_delete_order_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb_delete_nf.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    cq = DummyCallback(data="delete:999999", user_id=1, username="testuser")
    await cb_delete_order(cq)  # type: ignore[arg-type]
    
    # should answer with error alert
    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "订单不存在" in msg
    assert alert is True


@pytest.mark.asyncio
async def test_cb_delete_order_permission_denied(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)
    # set whitelist to exclude test user
    monkeypatch.setenv("ALLOWED_USER_IDS", "999")
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/cb_delete_perm.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    # create NEW order
    async with get_session() as session:
        order = await order_service.create_order(
            session,
            title="Test Permission Order",
            content="Test content",
            amount=300,
            created_by=1,
            created_by_username="testuser",
        )
        await session.commit()
    
    # try to delete with non-whitelisted user
    cq = DummyCallback(data=f"delete:{order.id}", user_id=1, username="testuser")
    await cb_delete_order(cq)  # type: ignore[arg-type]
    
    # should answer with permission denied alert
    assert cq.answered
    msg, alert = cq.answered[-1]
    assert "您没有权限执行此操作" in msg
    assert alert is True