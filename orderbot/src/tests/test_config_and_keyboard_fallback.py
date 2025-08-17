import pytest

from orderbot.src.config import Settings
from orderbot.src.tg.keyboards import order_action_kb


@pytest.mark.asyncio
async def test_operator_deeplink_priority_and_formats(monkeypatch):
    # priority: OPERATOR_USER_ID over OPERATOR_USERNAME
    monkeypatch.setenv("OPERATOR_USER_ID", "777")
    monkeypatch.setenv("OPERATOR_USERNAME", "opx")
    s = Settings()
    assert s.operator_deeplink() == "tg://user?id=777"

    # username only -> https link
    monkeypatch.setenv("OPERATOR_USER_ID", "")
    monkeypatch.setenv("OPERATOR_USERNAME", "opx")
    s = Settings()
    assert s.operator_deeplink() == "https://t.me/opx"

    # none -> None
    monkeypatch.delenv("OPERATOR_USER_ID", raising=False)
    monkeypatch.delenv("OPERATOR_USERNAME", raising=False)
    s = Settings()
    assert s.operator_deeplink() is None


@pytest.mark.asyncio
async def test_keyboard_fallback_to_user_id_when_no_username():
    kb = order_action_kb(order_id=1, operator_id=7, operator_username=None)
    rows = kb.inline_keyboard
    assert rows[1][1].url == "tg://user?id=7"
