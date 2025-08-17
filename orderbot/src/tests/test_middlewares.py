from __future__ import annotations

import asyncio

import pytest
from aiogram.types import User

from orderbot.src.tg.middlewares import WhitelistMiddleware, RateLimitMiddleware, ErrorHandlingMiddleware
from orderbot.src.config import Settings


class DummyMessage:
    def __init__(self, user_id: int, text: str = "/update foo") -> None:
        self.from_user = User(id=user_id, is_bot=False, first_name="U")
        self.text = text
        self.answered: list[str] = []

    async def answer(self, text: str, *_, **__):
        self.answered.append(text)


class DummyCallback:
    def __init__(self, user_id: int, data: str = "claim:1") -> None:
        self.from_user = User(id=user_id, is_bot=False, first_name="U")
        self.data = data
        self.answered: list[tuple[str, bool]] = []

    async def answer(self, text: str, show_alert: bool = False):
        self.answered.append((text, show_alert))


@pytest.mark.asyncio
async def test_whitelist_allows_when_empty(monkeypatch):
    monkeypatch.delenv("ALLOWED_USER_IDS", raising=False)
    settings = Settings()  # no ALLOWED_USER_IDS -> empty set
    mw = WhitelistMiddleware(settings)

    async def handler(ev, data):
        return "ok"

    msg = DummyMessage(123)
    res = await mw(handler, msg, {})
    assert res == "ok"


@pytest.mark.asyncio
async def test_whitelist_blocks_when_not_in_list(monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "1,2,3")
    settings = Settings()
    mw = WhitelistMiddleware(settings)

    msg = DummyMessage(999)

    async def handler(ev, data):
        return "should-not-run"

    res = await mw(handler, msg, {})
    await asyncio.sleep(0)  # allow scheduled answers
    assert res is None
    assert any("没有权限" in s or "无权" in s for s in msg.answered)


@pytest.mark.asyncio
async def test_ratelimit_blocks_frequent_calls():
    mw = RateLimitMiddleware(min_interval_seconds=0.2)

    cb = DummyCallback(5, data="claim:10")

    async def handler(ev, data):
        return "ok"

    # first pass
    r1 = await mw(handler, cb, {})
    # second immediately -> blocked
    r2 = await mw(handler, cb, {})
    await asyncio.sleep(0)

    assert r1 == "ok"
    assert r2 is None
    assert any("操作过于频繁" in t for t, _ in cb.answered)

    # wait then allowed again
    await asyncio.sleep(0.25)
    r3 = await mw(handler, cb, {})
    assert r3 == "ok"


@pytest.mark.asyncio
async def test_error_handling_middleware_catches_exceptions():
    mw = ErrorHandlingMiddleware()

    msg = DummyMessage(1)

    async def handler(ev, data):  # raises
        raise RuntimeError("boom")

    res = await mw(handler, msg, {})
    await asyncio.sleep(0)
    assert res is None
    assert any("发生错误" in s for s in msg.answered)