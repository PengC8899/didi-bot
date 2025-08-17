import os
import importlib
import pytest

from ..tg.keyboards import order_action_kb
from ..core.models import Order, OrderStatus


@pytest.mark.asyncio
async def test_order_action_keyboard_buttons():
    kb = order_action_kb(order_id=42, operator_id=7, operator_username="op")
    rows = kb.inline_keyboard
    assert len(rows) == 2
    assert rows[0][0].callback_data == "claim:42"
    assert rows[0][1].callback_data == "progress:42"
    assert rows[0][2].callback_data == "done:42"
    assert rows[1][0].callback_data == "cancel:42"
    assert rows[1][1].url.endswith("/op")


@pytest.mark.asyncio
async def test_channel_publish_skips_without_config(monkeypatch):
    # Ensure no env present before importing module to snapshot settings
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)

    import orderbot.src.services.channel_publisher as cp
    importlib.reload(cp)

    order = Order(title="t", content="c", amount=None, status=OrderStatus.NEW, created_by=1, created_by_username="u")
    mid = await cp.publish_order_to_channel(order)
    assert mid is None


@pytest.mark.asyncio
async def test_channel_edit_skips_without_config(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.delenv("CHANNEL_ID", raising=False)

    import orderbot.src.services.channel_publisher as cp
    importlib.reload(cp)

    order = Order(title="t2", content="c2", amount=None, status=OrderStatus.NEW, created_by=1, created_by_username="u")
    order.channel_message_id = 123
    # should not raise
    await cp.edit_order_message(order)
