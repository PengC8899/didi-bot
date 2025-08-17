import os
import pytest

from aiogram.types import Message
from ..core.db import init_engine
from ..tg.bot import router


class DummyMsg:
    def __init__(self, text: str):
        self.text = text
        self.from_user = type("U", (), {"id": 1, "username": "u"})
        self.answers: list[str] = []
        self._answered = None

    async def answer(self, text: str, reply_markup=None):
        # simulate sending; store last and history
        self._answered = text
        self.answers.append(text)
        # store reply_markup for testing
        self.last_reply_markup = reply_markup


@pytest.mark.asyncio
async def test_neworder_parse_and_response(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/test4.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    msg = DummyMsg("/neworder 标题 | 内容 | 9.9")
    # call handler directly
    from ..tg.bot import cmd_neworder

    await cmd_neworder(msg)  # type: ignore[arg-type]
    assert hasattr(msg, "_answered")
    assert "已创建工单" in msg._answered


# ---- New tests for interactive FSM flow ----
class DummyState:
    def __init__(self):
        self._state = None
        self._data: dict = {}

    async def get_state(self):
        return self._state

    async def set_state(self, s):
        self._state = s

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def get_data(self):
        return dict(self._data)

    async def clear(self):
        self._state = None
        self._data = {}


@pytest.mark.asyncio
async def test_neworder_interactive_flow_success(tmp_path, monkeypatch):
    # ensure channel publisher is skipped in tests
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)

    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/fsm1.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    from ..tg.bot import cmd_neworder, on_title, on_content, on_amount, on_confirm

    state = DummyState()
    msg = DummyMsg("/neworder")

    # start -> ask title
    await cmd_neworder(msg, state)  # type: ignore[arg-type]
    assert "请输入工单标题" in msg.answers[-1]
    assert await state.get_state() is not None

    # provide title -> ask content
    msg2 = DummyMsg("我的标题")
    await on_title(msg2, state)  # type: ignore[arg-type]
    assert "请输入工单内容" in msg2.answers[-1]

    # provide content -> ask amount
    msg3 = DummyMsg("我的内容")
    await on_content(msg3, state)  # type: ignore[arg-type]
    assert "请输入金额" in msg3.answers[-1]

    # provide amount -> go confirming
    msg4 = DummyMsg("0")  # 0 means no amount
    await on_amount(msg4, state)  # type: ignore[arg-type]
    assert "请确认创建工单" in msg4.answers[-1]

    # confirm
    msg5 = DummyMsg("确认")
    await on_confirm(msg5, state)  # type: ignore[arg-type]
    assert "已创建工单" in msg5.answers[-1]


@pytest.mark.asyncio
async def test_cancel_during_flow(tmp_path):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/fsm2.db"
    await init_engine(os.environ["DATABASE_URL"])  # create tables

    from ..tg.bot import cmd_neworder, cmd_cancel

    state = DummyState()
    msg = DummyMsg("/neworder")

    # start -> ask title (now in a state)
    await cmd_neworder(msg, state)  # type: ignore[arg-type]
    assert await state.get_state() is not None

    # cancel command should clear state
    msg_cancel = DummyMsg("/cancel")
    await cmd_cancel(msg_cancel, state)  # type: ignore[arg-type]
    assert await state.get_state() is None
    assert "已取消" in msg_cancel.answers[-1]


@pytest.mark.asyncio
async def test_myorders_whitelist_user_with_buttons(tmp_path, monkeypatch):
    """Test that whitelisted users see buttons in /myorders command"""
    # set whitelist to include test user
    monkeypatch.setenv("ALLOWED_USER_IDS", "1")
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/myorders_wl.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    # create some test orders
    from ..services import order_service
    from ..core.db import get_session
    
    async with get_session() as session:
        await order_service.create_order(
            session,
            title="Test Order 1",
            content="Content 1",
            amount=100,
            created_by=1,
            created_by_username="testuser",
        )
        await order_service.create_order(
            session,
            title="Test Order 2",
            content="Content 2",
            amount=None,
            created_by=1,
            created_by_username="testuser",
        )
        await session.commit()
    
    # patch the settings in bot module to use updated env vars
    from ..config import Settings
    from ..tg import bot
    bot.settings = Settings()  # recreate settings with new env vars
    
    from ..tg.bot import cmd_myorders
    
    msg = DummyMsg("/myorders")
    msg.from_user.id = 1  # whitelisted user
    msg.from_user.username = "testuser"
    
    await cmd_myorders(msg)  # type: ignore[arg-type]
    
    # should contain order information and buttons should be available
    # (we can't easily test keyboard in unit tests, but we can verify the response)
    assert msg._answered is not None
    assert "点击按钮进行操作" in msg._answered
    # verify that reply_markup (keyboard) was provided
    assert hasattr(msg, 'last_reply_markup')
    assert msg.last_reply_markup is not None


@pytest.mark.asyncio
async def test_myorders_non_whitelist_user_no_buttons(tmp_path, monkeypatch):
    """Test that non-whitelisted users see plain text in /myorders command"""
    # set whitelist to exclude test user
    monkeypatch.setenv("ALLOWED_USER_IDS", "999")
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/myorders_no_wl.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    # create some test orders
    from ..services import order_service
    from ..core.db import get_session
    
    async with get_session() as session:
        await order_service.create_order(
            session,
            title="Test Order 3",
            content="Content 3",
            amount=200,
            created_by=1,
            created_by_username="testuser",
        )
        await session.commit()
    
    # patch the settings in bot module to use updated env vars
    from ..config import Settings
    from ..tg import bot
    bot.settings = Settings()  # recreate settings with new env vars
    
    from ..tg.bot import cmd_myorders
    
    msg = DummyMsg("/myorders")
    msg.from_user.id = 1  # non-whitelisted user
    msg.from_user.username = "testuser"
    
    await cmd_myorders(msg)  # type: ignore[arg-type]
    
    # should contain order information but no interactive elements
    assert msg._answered is not None
    assert "Test Order 3" in msg._answered
    # no buttons for non-whitelisted users
    assert "点击按钮进行操作" not in msg._answered
    # verify that no reply_markup (keyboard) was provided
    assert not hasattr(msg, 'last_reply_markup') or msg.last_reply_markup is None


@pytest.mark.asyncio
async def test_myorders_no_orders(tmp_path, monkeypatch):
    """Test /myorders command when user has no orders"""
    monkeypatch.setenv("ALLOWED_USER_IDS", "1")
    
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path}/myorders_empty.db"
    await init_engine(os.environ["DATABASE_URL"])
    
    from ..tg.bot import cmd_myorders
    
    msg = DummyMsg("/myorders")
    msg.from_user.id = 1
    msg.from_user.username = "testuser"
    
    await cmd_myorders(msg)  # type: ignore[arg-type]
    
    # should indicate no orders found
    assert msg._answered is not None
    assert "没有找到" in msg._answered or "暂无" in msg._answered
