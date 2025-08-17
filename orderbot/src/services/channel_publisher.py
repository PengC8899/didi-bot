from __future__ import annotations

import asyncio
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from ..config import Settings
from ..core.models import Order, OrderStatus
from ..utils.logging import log_info, log_error, log_warn


_SETTINGS = Settings()
_BOT: Optional[Bot] = None


def _has_telegram_config() -> bool:
    try:
        return bool(_SETTINGS.BOT_TOKEN and _SETTINGS.CHANNEL_ID and int(_SETTINGS.CHANNEL_ID))
    except Exception:  # noqa: BLE001
        return False


def _ensure_bot() -> Bot:
    global _BOT
    if _BOT is None:
        from aiogram import Bot as _B
        _BOT = _B(token=_SETTINGS.BOT_TOKEN)
    return _BOT


def _render_order_text(order: Order) -> str:
    """渲染订单文本"""
    lines: list[str] = []
    lines.append(f"📋 {order.title}")
    lines.append(f"\n{order.content}")
    if order.amount is not None:
        lines.append(f"\n💰 金额：{order.amount}")
    lines.append(f"\n🆔 订单编号：#{order.id}")
    return "\n".join(lines)


def _create_simple_keyboard() -> InlineKeyboardMarkup:
    """创建简化的键盘，只有一个跳转私聊的按钮"""
    # 获取运营联系方式
    operator_username = _SETTINGS.OPERATOR_USERNAME
    operator_user_id = _SETTINGS.OPERATOR_USER_ID
    
    if operator_username:
        # 使用用户名跳转私聊
        contact_url = f"https://t.me/{operator_username.lstrip('@')}"
    elif operator_user_id:
        # 使用用户ID跳转私聊
        contact_url = f"tg://user?id={operator_user_id}"
    else:
        # 默认跳转到bot
        bot_username = _SETTINGS.BOT_USERNAME
        if bot_username:
            contact_url = f"https://t.me/{bot_username.lstrip('@')}"
        else:
            contact_url = "https://t.me/your_bot_username"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 联系接单", url=contact_url)]
    ])
    return keyboard


async def publish_order_to_channel(order: Order, image_path: Optional[str] = None) -> Optional[int]:
    """发布订单到频道，支持图片"""
    if not _has_telegram_config():
        log_warn("channel_publisher.no_config")
        return None
    
    bot = _ensure_bot()
    text = _render_order_text(order)
    keyboard = _create_simple_keyboard()
    
    try:
        if image_path:
            # 发送带图片的消息
            photo = FSInputFile(image_path)
            message = await bot.send_photo(
                chat_id=int(_SETTINGS.CHANNEL_ID),
                photo=photo,
                caption=text,
                reply_markup=keyboard
            )
        else:
            # 发送纯文本消息
            message = await bot.send_message(
                chat_id=int(_SETTINGS.CHANNEL_ID),
                text=text,
                reply_markup=keyboard
            )
        
        log_info("channel_publisher.published", order_id=order.id, message_id=message.message_id)
        return message.message_id
        
    except Exception as e:
        log_error("channel_publisher.failed", order_id=order.id, error=str(e))
        return None


async def edit_order_message(order: Order, image_path: Optional[str] = None) -> bool:
    """编辑频道中的订单消息"""
    if not _has_telegram_config() or not order.channel_message_id:
        return False
    
    bot = _ensure_bot()
    text = _render_order_text(order)
    keyboard = _create_simple_keyboard()
    
    try:
        if image_path:
            # 对于有图片的消息，只能编辑caption
            await bot.edit_message_caption(
                chat_id=int(_SETTINGS.CHANNEL_ID),
                message_id=order.channel_message_id,
                caption=text,
                reply_markup=keyboard
            )
        else:
            # 编辑纯文本消息
            await bot.edit_message_text(
                chat_id=int(_SETTINGS.CHANNEL_ID),
                message_id=order.channel_message_id,
                text=text,
                reply_markup=keyboard
            )
        
        log_info("channel_publisher.edited", order_id=order.id, message_id=order.channel_message_id)
        return True
        
    except Exception as e:
        log_error("channel_publisher.edit_failed", order_id=order.id, error=str(e))
        return False
