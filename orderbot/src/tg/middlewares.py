from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Set, TypeVar

from ..config import Settings
from ..utils.logging import log_error, log_info

Event = TypeVar("Event")
Handler = Callable[[Event, Dict[str, Any]], Awaitable[Any]]


def _extract_user_id(event: Any) -> Optional[int]:
    user = getattr(event, "from_user", None)
    if user is None:
        return None
    return getattr(user, "id", None)


def _safe_answer(event: Any, text: str, *, prefer_alert: bool = False) -> None:
    ans = getattr(event, "answer", None)
    if ans is None or not callable(ans):
        return
    try:
        if prefer_alert:
            # Try show_alert if supported (CallbackQuery-compatible)
            asyncio.create_task(ans(text, show_alert=True))  # type: ignore[misc]
            return None
        asyncio.create_task(ans(text))  # type: ignore[misc]
        return None
    except Exception:  # noqa: BLE001
        return None


class WhitelistMiddleware:
    """Whitelist auth middleware.

    If ALLOWED_USER_IDS is empty -> allow all (fallback to other checks as per ALIGNMENT).
    Otherwise, only allow users whose id is present in the whitelist.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._allowed: Set[int] = self.settings.allowed_user_ids()

    async def __call__(self, handler: Handler, event: Event, data: Dict[str, Any]) -> Any:  # type: ignore[override]
        user_id = _extract_user_id(event)

        if not self._allowed:
            return await handler(event, data)

        if user_id is None or user_id not in self._allowed:
            # deny politely
            prefer_alert = hasattr(event, "data")
            _safe_answer(event, "您没有权限执行此操作。" if not prefer_alert else "无权操作", prefer_alert=prefer_alert)
            log_info("auth.denied", actor_tg_user_id=user_id)
            return None
        return await handler(event, data)


class RateLimitMiddleware:
    """Simple in-memory rate limit per user for key operations.

    Compatible params:
    - min_interval_seconds: minimal interval between allowed calls for a given user/key
    - OR legacy style: max_calls per `per_seconds` window (we only use it to compute interval)
    """

    def __init__(self, min_interval_seconds: float = 5.0, *, max_calls: int | None = None, per_seconds: float | None = None) -> None:
        # Backward-compatible constructor: if legacy style provided, derive minimal interval
        self._limit_all_messages = False
        if max_calls is not None or per_seconds is not None:
            # sanitize inputs
            mc = max_calls or 1
            window = per_seconds or float(min_interval_seconds)
            if mc <= 0:
                mc = 1
            # minimal interval between calls when allowing mc calls per window
            self.min_interval = float(window) / float(mc)
            # legacy tests expect any text message to be rate-limited
            self._limit_all_messages = True
        else:
            self.min_interval = float(min_interval_seconds)
        self._last: Dict[tuple[str, int], float] = {}
        self._lock = asyncio.Lock()

    def _key(self, event: Any) -> Optional[tuple[str, int]]:
        uid = _extract_user_id(event)
        if uid is None:
            return None
        data = getattr(event, "data", None)
        if isinstance(data, str) and (any(data.startswith(p) for p in ("claim:", "progress:", "done:", "cancel:", "apply:")) or data in {"list", "publish_start"}):
            return ("cb", uid)
        text = getattr(event, "text", None)
        if isinstance(text, str):
            s = text.strip()
            if not s:
                return None
            if self._limit_all_messages:
                return ("msg_any", uid)
            if s.startswith("/update"):
                return ("msg_update", uid)
        return None

    async def __call__(self, handler: Handler, event: Event, data: Dict[str, Any]) -> Any:  # type: ignore[override]
        k = self._key(event)
        if not k:
            return await handler(event, data)
        async with self._lock:
            now = time.monotonic()
            last = self._last.get(k, 0.0)
            if now - last < self.min_interval:
                _safe_answer(event, "操作过于频繁，请稍后再试", prefer_alert=(k[0] == "cb"))
                log_info("ratelimit.block", key=k[0], actor_tg_user_id=k[1])
                return None
            self._last[k] = now
        return await handler(event, data)


class ErrorHandlingMiddleware:
    """Catch and log unhandled exceptions from handlers to avoid crash."""

    async def __call__(self, handler: Handler, event: Event, data: Dict[str, Any]) -> Any:  # type: ignore[override]
        try:
            return await handler(event, data)
        except Exception as e:  # noqa: BLE001
            actor_id = _extract_user_id(event)
            log_error("handler.error", error=str(e), actor_tg_user_id=actor_id)
            _safe_answer(event, "发生错误，请稍后再试", prefer_alert=hasattr(event, "data"))
            return None