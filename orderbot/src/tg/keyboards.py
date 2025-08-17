from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from typing import List

from ..core.models import OrderStatus


# Callback data constants
CLAIM_CB = "claim:{order_id}"
PROGRESS_CB = "progress:{order_id}"
DONE_CB = "done:{order_id}"
CANCEL_CB = "cancel:{order_id}"
APPLY_CB = "apply:{order_id}"
LIST_CB = "list"
PUBLISH_START_CB = "publish_start"
PUBLISH_ORDER_CB = "publish_order:{order_id}"
DELETE_ORDER_CB = "delete_order:{order_id}"
APPROVE_CB = "approve:{order_id}:{app_id}"
REJECT_CB = "reject:{order_id}:{app_id}"
DRAFT_APPROVE_CB = "draft_approve:{order_id}"
DRAFT_REJECT_CB = "draft_reject:{order_id}"

# New callback data for main menu
PUBLISH_ORDER_MENU_CB = "menu_publish_order"
ORDER_LIST_CB = "menu_order_list"
AMOUNT_STATS_CB = "menu_amount_stats"
ADMIN_LIST_CB = "menu_admin_list"
BACK_TO_MAIN_CB = "back_to_main"
REFRESH_ORDERS_CB = "refresh_orders"
ORDER_STATS_CB = "order_stats"
STATS_TODAY_CB = "stats_today"
STATS_WEEK_CB = "stats_week"
STATS_MONTH_CB = "stats_month"
STATS_CUSTOM_CB = "stats_custom"
ADMIN_ADD_CB = "admin_add"
ADMIN_REMOVE_CB = "admin_remove"
ADMIN_LIST_VIEW_CB = "admin_list_view"
CONFIRM_CB = "confirm_{action}"
CANCEL_ACTION_CB = "cancel_action"


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """获取主菜单键盘"""
    builder = ReplyKeyboardBuilder()
    
    # 第一行：发布订单、订单列表
    builder.add(KeyboardButton(text="📝 发布订单"))
    builder.add(KeyboardButton(text="📋 订单列表"))
    
    # 第二行：金额统计、管理员列表
    builder.add(KeyboardButton(text="💰 金额统计"))
    builder.add(KeyboardButton(text="👥 管理员列表"))
    
    # 设置键盘布局为2列
    builder.adjust(2)
    
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="请选择功能..."
    )


def get_order_list_keyboard(has_orders: bool = True) -> InlineKeyboardMarkup:
    """获取订单列表操作键盘"""
    builder = InlineKeyboardBuilder()
    
    if has_orders:
        builder.add(InlineKeyboardButton(text="🔄 刷新列表", callback_data=REFRESH_ORDERS_CB))
        builder.add(InlineKeyboardButton(text="📊 详细统计", callback_data=ORDER_STATS_CB))
    
    builder.add(InlineKeyboardButton(text="🏠 返回主菜单", callback_data=BACK_TO_MAIN_CB))
    
    builder.adjust(2 if has_orders else 1)
    return builder.as_markup()


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """获取金额统计键盘"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="📅 今日统计", callback_data=STATS_TODAY_CB))
    builder.add(InlineKeyboardButton(text="📆 本周统计", callback_data=STATS_WEEK_CB))
    builder.add(InlineKeyboardButton(text="🗓️ 本月统计", callback_data=STATS_MONTH_CB))
    builder.add(InlineKeyboardButton(text="📈 自定义日期", callback_data=STATS_CUSTOM_CB))
    builder.add(InlineKeyboardButton(text="🏠 返回主菜单", callback_data=BACK_TO_MAIN_CB))
    
    builder.adjust(2)
    return builder.as_markup()


def get_admin_list_keyboard() -> InlineKeyboardMarkup:
    """获取管理员列表键盘"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="➕ 添加管理员", callback_data=ADMIN_ADD_CB))
    builder.add(InlineKeyboardButton(text="➖ 删除管理员", callback_data=ADMIN_REMOVE_CB))
    builder.add(InlineKeyboardButton(text="📋 查看列表", callback_data=ADMIN_LIST_VIEW_CB))
    builder.add(InlineKeyboardButton(text="🏠 返回主菜单", callback_data=BACK_TO_MAIN_CB))
    
    builder.adjust(2)
    return builder.as_markup()


def get_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """获取确认操作键盘"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="✅ 确认", callback_data=f"confirm_{action}"))
    builder.add(InlineKeyboardButton(text="❌ 取消", callback_data=CANCEL_ACTION_CB))
    
    builder.adjust(2)
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """获取返回键盘"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🏠 返回主菜单", callback_data=BACK_TO_MAIN_CB))
    return builder.as_markup()


# Legacy functions for compatibility
def order_action_kb(order_id: int, operator_id: int, operator_username: str | None) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    # Row 1: claim / in progress / done
    buttons.append(
        [
            InlineKeyboardButton(text="认领", callback_data=CLAIM_CB.format(order_id=order_id)),
            InlineKeyboardButton(text="进行中", callback_data=PROGRESS_CB.format(order_id=order_id)),
            InlineKeyboardButton(text="完成", callback_data=DONE_CB.format(order_id=order_id)),
        ]
    )
    # Row 2: cancel and operator deep-link
    op_text = f"联系运营({operator_username})" if operator_username else "联系运营"
    operator_url = f"https://t.me/{operator_username.lstrip('@')}" if operator_username else f"tg://user?id={operator_id}"
    buttons.append(
        [
            InlineKeyboardButton(text="取消", callback_data=CANCEL_CB.format(order_id=order_id)),
            InlineKeyboardButton(text=op_text, url=operator_url),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def channel_public_kb(order_id: int, operator_id: int, operator_username: str | None, bot_username: str | None) -> InlineKeyboardMarkup:
    """频道贴文使用的公共交互键盘（两个按钮）：「接单」跳转到运营私聊，「发布」跳转到Bot引导发单。"""
    buttons = []
    
    # 接单按钮 - 直接跳转到运营私聊
    if operator_username:
        operator_url = f"https://t.me/{operator_username.lstrip('@')}"
    else:
        operator_url = f"tg://user?id={operator_id}" if operator_id else None
    
    if operator_url:
        buttons.append(InlineKeyboardButton(text="接单", url=operator_url))
    else:
        buttons.append(InlineKeyboardButton(text="接单", callback_data="noop"))
    
    # 发布按钮 - 跳转到Bot引导发单
    uname = (bot_username or "").lstrip("@")
    bot_url = f"https://t.me/{uname}?start=publish_order" if uname else None
    
    if bot_url:
        buttons.append(InlineKeyboardButton(text="发布", url=bot_url))
    else:
        buttons.append(InlineKeyboardButton(text="发布", callback_data="noop"))
    
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def main_menu_kb() -> ReplyKeyboardMarkup:
    """私聊主菜单：提供直观入口。

    - 📝 发布订单 -> 发送 /neworder
    - 📋 我的工单 -> 发送 /myorders
    - ❌ 取消 -> 发送 /cancel
    """
    return get_main_keyboard()


def review_applications_kb(order_id: int, applications: list[tuple[int, str | None, int]]) -> InlineKeyboardMarkup:
    """生成审核用键盘。

    applications: 列表项为 (app_id, applicant_username, applicant_tg_id)
    每一行两个按钮：✅同意 / ❌拒绝
    """
    rows: list[list[InlineKeyboardButton]] = []
    for app_id, applicant_username, applicant_tg_id in applications:
        name = applicant_username or f"#{applicant_tg_id}"
        rows.append(
            [
                InlineKeyboardButton(text=f"✅同意 {name}", callback_data=APPROVE_CB.format(order_id=order_id, app_id=app_id)),
                InlineKeyboardButton(text=f"❌拒绝 {name}", callback_data=REJECT_CB.format(order_id=order_id, app_id=app_id)),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def draft_review_kb(order_id: int) -> InlineKeyboardMarkup:
    """草稿审核键盘：✅发布到频道 / ❌退回修改"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ 发布到频道", callback_data=DRAFT_APPROVE_CB.format(order_id=order_id)),
                InlineKeyboardButton(text="❌ 退回修改", callback_data=DRAFT_REJECT_CB.format(order_id=order_id)),
            ]
        ]
    )


def start_menu_kb(order_id: int) -> InlineKeyboardMarkup:
    """私聊 /start menu_<order_id> 时展示的二选一菜单：接单/发单"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="接单", callback_data=APPLY_CB.format(order_id=order_id)),
                InlineKeyboardButton(text="发单", callback_data=PUBLISH_START_CB),
            ]
        ]
    )


def myorders_kb(orders: list[tuple[int, str, str, str | None]]) -> InlineKeyboardMarkup:
    """我的订单列表键盘，每个订单显示发布和删除按钮。
    
    Args:
        orders: 订单列表，每项为 (order_id, title, status, contact_username)
    """
    rows: list[list[InlineKeyboardButton]] = []
    for order_id, title, status, contact_username in orders:
        # 每个订单一行，显示标题、状态和联系方式
        contact_info = f" (联系: {contact_username})" if contact_username else ""
        order_text = f"#{order_id} {title[:15]}{'...' if len(title) > 15 else ''} [{status}]{contact_info}"
        rows.append([InlineKeyboardButton(text=order_text, callback_data="noop")])
        
        # 下一行显示发布和删除按钮
        action_buttons = [
            InlineKeyboardButton(text="📤 发布", callback_data=PUBLISH_ORDER_CB.format(order_id=order_id)),
            InlineKeyboardButton(text="🗑️ 删除", callback_data=DELETE_ORDER_CB.format(order_id=order_id)),
        ]
        rows.append(action_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=rows)
