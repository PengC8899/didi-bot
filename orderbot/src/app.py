import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有安装 python-dotenv，跳过
    pass

from .config import Settings
from .tg.bot import setup_bot


async def main() -> None:
    """Application entrypoint: start long polling bot."""
    settings = Settings()  # loads from env

    # Configure basic logging early
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Setup bot (routes, db, etc.)
    await setup_bot(dp)

    try:
        await dp.start_polling(bot)
    except Exception:  # noqa: BLE001
        logging.exception("bot.polling.error")
        raise


if __name__ == "__main__":
    asyncio.run(main())
