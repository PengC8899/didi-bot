from __future__ import annotations

import json
import logging
import os
from typing import Any

_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=getattr(logging, _LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("orderbot")


def _kv(**kwargs: Any) -> str:
    try:
        return json.dumps(kwargs, ensure_ascii=False, separators=(",", ":"))
    except Exception:  # noqa: BLE001
        return str(kwargs)


def log_info(event: str, **kwargs: Any) -> None:
    logger.info("%s %s", event, _kv(**kwargs))


def log_error(event: str, **kwargs: Any) -> None:
    logger.error("%s %s", event, _kv(**kwargs))


def log_warn(event: str, **kwargs: Any) -> None:
    logger.warning("%s %s", event, _kv(**kwargs))
