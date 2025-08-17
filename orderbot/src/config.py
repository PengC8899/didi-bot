from __future__ import annotations

from typing import Optional, Set
from pydantic import BaseModel, Field
import os


class Settings(BaseModel):
    """Application settings loaded from environment variables.

    Note: this is a lightweight wrapper (not BaseSettings) to avoid pydantic v1/v2 differences; we read from os.environ.
    """

    BOT_TOKEN: str = Field(default_factory=lambda: os.environ.get("BOT_TOKEN", ""))
    CHANNEL_ID: str = Field(default_factory=lambda: os.environ.get("CHANNEL_ID", ""))
    OPERATOR_USER_ID: Optional[str] = Field(default_factory=lambda: os.environ.get("OPERATOR_USER_ID"))
    OPERATOR_USERNAME: Optional[str] = Field(default_factory=lambda: os.environ.get("OPERATOR_USERNAME"))
    BOT_USERNAME: Optional[str] = Field(default_factory=lambda: os.environ.get("BOT_USERNAME"))
    ALLOWED_USER_IDS: str = Field(default_factory=lambda: os.environ.get("ALLOWED_USER_IDS", ""))

    DATABASE_URL: str = Field(default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./orderbot.db"))
    LOG_LEVEL: str = Field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    def allowed_user_ids(self) -> Set[int]:
        """Parse ALLOWED_USER_IDS env to a set of ints.

        Empty means no explicit whitelist; handlers/middleware will fallback to channel-membership checks as documented.
        """
        raw = (self.ALLOWED_USER_IDS or "").strip()
        ids: Set[int] = set()
        if not raw:
            return ids
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                ids.add(int(part))
            except ValueError:
                # ignore invalid piece silently; middlewares will treat as not whitelisted
                continue
        return ids

    def channel_id_int(self) -> int:
        return int(self.CHANNEL_ID)

    def operator_deeplink(self) -> Optional[str]:
        if self.OPERATOR_USER_ID:
            return f"tg://user?id={self.OPERATOR_USER_ID}"
        if self.OPERATOR_USERNAME:
            username = self.OPERATOR_USERNAME.lstrip("@")
            return f"https://t.me/{username}"
        return None

    def bot_apply_deeplink(self, order_id: int) -> Optional[str]:
        """生成与 Bot 的 start 深链，例如 https://t.me/<bot_username>?start=apply_<order_id>。
        若未配置 `BOT_USERNAME`，返回 None。
        """
        if not self.BOT_USERNAME:
            return None
        username = self.BOT_USERNAME.lstrip("@")
        return f"https://t.me/{username}?start=apply_{order_id}"
