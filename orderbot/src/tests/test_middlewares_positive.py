import asyncio
import pytest

from orderbot.src.tg.middlewares import WhitelistMiddleware, RateLimitMiddleware
from orderbot.src.config import Settings


class DummyMessage:
    def __init__(self, user_id: int, text: str = "/start") -> None:
        from aiogram.types import User
        self.from_user = User(id=user_id, is_bot=False, first_name="U")
        self.text = text
        self.answered: list[str] = []

    async def answer(self, text: str, *_, **__):
        self.answered.append(text)


@pytest.mark.asyncio
async def test_whitelist_allows_specific_users(monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "1,2,3")
    settings = Settings()
    mw = WhitelistMiddleware(settings)

    async def handler(ev, data):
        return "ok"

    msg = DummyMessage(2)
    res = await mw(handler, msg, {})
    assert res == "ok"


@pytest.mark.asyncio
async def test_rate_limit_allows_single_call():
    mw = RateLimitMiddleware(max_calls=1, per_seconds=0.1)

    async def handler(ev, data):
        return "ok"

    msg = DummyMessage(5)
    res = await mw(handler, msg, {})
    assert res == "ok"


@pytest.mark.asyncio
async def test_rate_limit_blocks_second_call_then_allows_after_window():
    mw = RateLimitMiddleware(max_calls=1, per_seconds=0.05)

    async def handler(ev, data):
        return "ok"

    msg = DummyMessage(6)

    # first allowed
    res1 = await mw(handler, msg, {})
    assert res1 == "ok"

    # second should be rate limited
    res2 = await mw(handler, msg, {})
    await asyncio.sleep(0)  # allow async answer scheduling
    assert res2 is None

    # wait for window then allowed again
    await asyncio.sleep(0.06)
    res3 = await mw(handler, msg, {})
    assert res3 == "ok"