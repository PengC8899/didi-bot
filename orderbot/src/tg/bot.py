from __future__ import annotations

from aiogram import Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PhotoSize
from datetime import datetime, timedelta
from aiogram.fsm.context import FSMContext
import os
import aiofiles

from ..config import Settings
from ..core.db import get_session, init_engine
from ..core.models import OrderStatus
from ..services import order_service
from ..services.user_management import UserManagementService
from ..utils.logging import log_info, log_error
from ..utils.network import network_health_checker
from .middlewares import ErrorHandlingMiddleware, RateLimitMiddleware
from .fsm import OrderCreationFlow
from .keyboards import get_main_keyboard, get_order_list_keyboard, get_stats_keyboard, get_admin_list_keyboard, get_back_keyboard


settings = Settings()

# 图片存储目录
IMAGE_DIR = "/app/images"
os.makedirs(IMAGE_DIR, exist_ok=True)


router = Router()


@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext) -> None:
    """处理 /start 命令"""
    await state.clear()
    await msg.answer(
        "🏠 欢迎使用订单管理机器人！\n\n请选择功能：",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("发布"))
async def cmd_publish(msg: Message, state: FSMContext) -> None:
    """处理 /发布 命令"""
    await state.clear()
    await state.set_state(OrderCreationFlow.asking_content)
    await msg.answer("请输入订单详情：")


@router.message(Command("添加操作人"))
async def add_operator(message: Message) -> None:
    """添加操作人命令"""
    user_id = message.from_user.id if message.from_user else 0
    
    # 检查权限
    if user_id != 7411441877:
        await message.answer("❌ 您没有权限执行此操作")
        return
    
    # 解析命令参数
    command_parts = message.text.split()
    if len(command_parts) != 2:
        await message.answer("❌ 使用格式：/添加操作人 &lt;用户ID&gt;")
        return
    
    try:
        target_user_id = int(command_parts[1])
    except ValueError:
        await message.answer("❌ 用户ID必须是数字")
        return
    
    try:
        user_service = UserManagementService(settings)
        success = await user_service.add_operator(target_user_id)
        
        if success:
            await message.answer(f"✅ 已成功添加操作人：{target_user_id}")
            log_info("operator.added", user_id=target_user_id, by_user=user_id)
        else:
            await message.answer(f"⚠️ 用户 {target_user_id} 已经是操作人")
    except Exception as e:
        await message.answer(f"❌ 添加操作人失败：{str(e)}")
        log_error("operator.add.failed", error=str(e), target_user=target_user_id)


@router.message(Command("删除操作人"))
async def remove_operator(message: Message) -> None:
    """删除操作人命令"""
    user_id = message.from_user.id if message.from_user else 0
    
    # 检查权限
    if user_id != 7411441877:
        await message.answer("❌ 您没有权限执行此操作")
        return
    
    # 解析命令参数
    command_parts = message.text.split()
    if len(command_parts) != 2:
        await message.answer("❌ 使用格式：/删除操作人 &lt;用户ID&gt;")
        return
    
    try:
        target_user_id = int(command_parts[1])
    except ValueError:
        await message.answer("❌ 用户ID必须是数字")
        return
    
    try:
        user_service = UserManagementService(settings)
        success = await user_service.remove_operator(target_user_id)
        
        if success:
            await message.answer(f"✅ 已成功删除操作人：{target_user_id}")
            log_info("operator.removed", user_id=target_user_id, by_user=user_id)
        else:
            await message.answer(f"⚠️ 用户 {target_user_id} 不是操作人")
    except Exception as e:
        await message.answer(f"❌ 删除操作人失败：{str(e)}")
        log_error("operator.remove.failed", error=str(e), target_user=target_user_id)


# 主菜单按钮处理器
@router.message(F.text == "📝 发布订单")
async def handle_publish_order_button(msg: Message, state: FSMContext) -> None:
    """处理发布订单按钮"""
    await state.clear()
    await state.set_state(OrderCreationFlow.asking_content)
    await msg.answer("请输入订单详情：")


@router.message(F.text == "📋 订单列表")
async def handle_order_list_button(msg: Message, state: FSMContext) -> None:
    """处理订单列表按钮"""
    user_id = msg.from_user.id if msg.from_user else 0
    
    async with get_session() as session:
        try:
            # 获取用户的订单列表
            orders = await order_service.get_orders_by_user(session, user_id)
            
            if not orders:
                await msg.answer(
                    "📋 您还没有发布过订单\n\n"
                    "点击 📝 发布订单 开始创建您的第一个订单！",
                    reply_markup=get_order_list_keyboard(has_orders=False)
                )
                return
            
            # 构建订单列表消息
            order_text = "📋 您的订单列表：\n\n"
            for order in orders[:10]:  # 最多显示10个订单
                status_emoji = {
                    OrderStatus.DRAFT: "📄",
                    OrderStatus.NEW: "📝",
                    OrderStatus.CLAIMED: "📢",
                    OrderStatus.IN_PROGRESS: "🔄",
                    OrderStatus.DONE: "✅",
                    OrderStatus.CANCELED: "❌"
                }.get(order.status, "❓")
                
                order_text += f"{status_emoji} #{order.id} {order.title}\n"
                order_text += f"   💰 {order.amount}元 | {order.status.value}\n"
                order_text += f"   📅 {order.created_at.strftime('%m-%d %H:%M')}\n\n"
            
            if len(orders) > 10:
                order_text += f"... 还有 {len(orders) - 10} 个订单\n"
            
            await msg.answer(order_text, reply_markup=get_order_list_keyboard())
            
        except Exception as e:
            await msg.answer(f"❌ 获取订单列表失败：{str(e)}")
            log_error("order.list.failed", error=str(e))


@router.message(F.text == "💰 金额统计")
async def handle_amount_stats_button(msg: Message, state: FSMContext) -> None:
    """处理金额统计按钮"""
    await msg.answer(
        "💰 金额统计\n\n"
        "请选择统计时间范围：",
        reply_markup=get_stats_keyboard()
    )


@router.message(F.text == "👥 管理员列表")
async def handle_admin_list_button(msg: Message, state: FSMContext) -> None:
    """处理管理员列表按钮"""
    user_id = msg.from_user.id if msg.from_user else 0
    
    # 检查权限 - 只有特定用户可以使用
    if user_id != 7411441877:
        await msg.answer("❌ 您没有权限使用此功能")
        return
    
    await msg.answer(
        "👥 管理员列表\n\n"
        "请选择操作：",
        reply_markup=get_admin_list_keyboard()
    )


# 回调查询处理器
@router.callback_query(F.data == "back_to_main")
async def handle_back_to_main(callback: CallbackQuery) -> None:
    """返回主菜单"""
    # 删除当前内联键盘消息
    try:
        await callback.message.delete()
    except Exception:
        pass  # 忽略删除失败的情况
    
    # 发送新的主菜单消息
    await callback.message.answer(
        "🏠 主菜单\n\n请选择功能：",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "refresh_orders")
async def handle_refresh_orders(callback: CallbackQuery) -> None:
    """刷新订单列表"""
    user_id = callback.from_user.id if callback.from_user else 0
    
    async with get_session() as session:
        try:
            orders = await order_service.get_orders_by_user(session, user_id)
            
            if not orders:
                await callback.message.edit_text(
                    "📋 您还没有发布过订单\n\n"
                    "点击 📝 发布订单 开始创建您的第一个订单！",
                    reply_markup=get_order_list_keyboard(has_orders=False)
                )
                await callback.answer("列表已刷新")
                return
            
            # 构建订单列表消息
            order_text = "📋 您的订单列表：\n\n"
            for order in orders[:10]:
                status_emoji = {
                    OrderStatus.DRAFT: "📄",
                    OrderStatus.NEW: "📝",
                    OrderStatus.CLAIMED: "📢",
                    OrderStatus.IN_PROGRESS: "🔄",
                    OrderStatus.DONE: "✅",
                    OrderStatus.CANCELED: "❌"
                }.get(order.status, "❓")
                
                order_text += f"{status_emoji} #{order.id} {order.title}\n"
                order_text += f"   💰 {order.amount}元 | {order.status.value}\n"
                order_text += f"   📅 {order.created_at.strftime('%m-%d %H:%M')}\n\n"
            
            if len(orders) > 10:
                order_text += f"... 还有 {len(orders) - 10} 个订单\n"
            
            await callback.message.edit_text(order_text, reply_markup=get_order_list_keyboard())
            await callback.answer("列表已刷新")
            
        except Exception as e:
            await callback.answer(f"刷新失败：{str(e)}")
            log_error("order.refresh.failed", error=str(e))


@router.callback_query(F.data == "order_stats")
async def handle_order_stats_callback(callback: CallbackQuery) -> None:
    """处理订单详细统计回调"""
    await callback.message.edit_text(
        "📊 订单详细统计\n\n"
        "请选择统计时间范围：",
        reply_markup=get_stats_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stats_"))
async def handle_stats_callback(callback: CallbackQuery) -> None:
    """处理金额统计回调"""
    user_id = callback.from_user.id if callback.from_user else 0
    stats_type = callback.data.split("_")[1]  # today, week, month
    
    async with get_session() as session:
        try:
            # 计算时间范围
            now = datetime.now()
            if stats_type == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                period_name = "今日"
            elif stats_type == "week":
                start_date = now - timedelta(days=now.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                period_name = "本周"
            elif stats_type == "month":
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                period_name = "本月"
            else:
                await callback.answer("无效的统计类型")
                return
            
            # 获取订单数据
            orders = await order_service.get_orders_by_user_and_date_range(
                session, user_id, start_date, now
            )
            
            if not orders:
                await callback.message.edit_text(
                    f"💰 {period_name}金额统计\n\n"
                    f"📊 暂无{period_name}订单数据",
                    reply_markup=get_back_keyboard()
                )
                await callback.answer()
                return
            
            # 统计数据
            total_amount = sum(order.amount for order in orders)
            status_stats = {}
            for order in orders:
                status = order.status.value
                if status not in status_stats:
                    status_stats[status] = {"count": 0, "amount": 0}
                status_stats[status]["count"] += 1
                status_stats[status]["amount"] += order.amount
            
            # 构建统计消息
            stats_text = f"💰 {period_name}金额统计\n\n"
            stats_text += f"📊 总订单数：{len(orders)}\n"
            stats_text += f"💵 总金额：{total_amount}元\n\n"
            stats_text += "📈 按状态统计：\n"
            
            for status, data in status_stats.items():
                stats_text += f"   {status}：{data['count']}单，{data['amount']}元\n"
            
            await callback.message.edit_text(
                stats_text,
                reply_markup=get_back_keyboard()
            )
            await callback.answer()
            
        except Exception as e:
            await callback.answer(f"统计失败：{str(e)}")
            log_error("stats.failed", error=str(e), stats_type=stats_type)


@router.callback_query(F.data.startswith("admin_"))
async def handle_admin_callback(callback: CallbackQuery) -> None:
    """处理管理员操作回调"""
    user_id = callback.from_user.id if callback.from_user else 0
    
    # 检查权限
    if user_id != 7411441877:
        await callback.answer("❌ 您没有权限使用此功能")
        return
    
    action = callback.data.split("_")[1]  # add, remove, list
    
    try:
        user_service = UserManagementService(settings)
        
        if action == "list":
            # 获取管理员列表
            operators = await user_service.get_operators()
            
            if not operators:
                admin_text = "👥 管理员列表\n\n暂无管理员"
            else:
                admin_text = "👥 管理员列表\n\n"
                for i, op_id in enumerate(operators, 1):
                    admin_text += f"{i}. {op_id}\n"
            
            await callback.message.edit_text(
                admin_text,
                reply_markup=get_back_keyboard()
            )
        elif action == "add":
            await callback.message.edit_text(
                "➕ 添加管理员\n\n"
                "请使用命令：/添加操作人 &lt;用户ID&gt;",
                reply_markup=get_back_keyboard()
            )
        elif action == "remove":
            await callback.message.edit_text(
                "➖ 删除管理员\n\n"
                "请使用命令：/删除操作人 &lt;用户ID&gt;",
                reply_markup=get_back_keyboard()
            )
        else:
            await callback.answer("无效的操作")
            return
            
    except Exception as e:
        await callback.answer(f"获取管理员列表失败：{str(e)}")
        log_error("admin.list.failed", error=str(e))
    
    await callback.answer()


@router.message(OrderCreationFlow.asking_content)
async def on_content(msg: Message, state: FSMContext) -> None:
    """接收订单详情"""
    if not msg.text:
        await msg.answer("请输入文字内容作为订单详情")
        return
    
    await state.update_data(content=msg.text)
    await state.set_state(OrderCreationFlow.asking_amount)
    await msg.answer("请输入订单金额（数字）：")


@router.message(OrderCreationFlow.asking_amount)
async def on_amount(msg: Message, state: FSMContext) -> None:
    """接收订单金额"""
    if not msg.text:
        await msg.answer("请输入数字作为订单金额")
        return
    
    try:
        amount = float(msg.text)
        if amount <= 0:
            await msg.answer("订单金额必须大于0")
            return
    except ValueError:
        await msg.answer("请输入有效的数字")
        return
    
    # 获取状态数据
    data = await state.get_data()
    content = data.get("content", "")
    
    # 创建订单
    user_id = msg.from_user.id if msg.from_user else 0
    username = msg.from_user.username if msg.from_user else "未知用户"
    
    async with get_session() as session:
        try:
            order = await order_service.create_order(
                session=session,
                created_by=user_id,
                created_by_username=username,
                title=content[:50],  # 取前50个字符作为标题
                content=content,
                amount=amount
            )
            
            await msg.answer(
                f"✅ 订单创建成功！\n\n"
                f"订单编号：#{order.id}\n"
                f"订单详情：{content}\n"
                f"订单金额：{amount}元\n\n"
                f"您可以继续上传图片，或发送其他消息结束创建。"
            )
            
            # 保存订单ID到状态，用于图片上传
            await state.update_data(order_id=order.id)
            
        except Exception as e:
            await msg.answer(f"❌ 创建订单失败：{str(e)}")
            log_error("order.create.failed", error=str(e))
    
    await state.clear()


@router.message(F.photo)
async def on_photo(msg: Message, state: FSMContext) -> None:
    """处理图片上传"""
    if not msg.photo:
        return
    
    # 获取最大尺寸的图片
    photo: PhotoSize = msg.photo[-1]
    
    try:
        # 下载图片
        file_info = await msg.bot.get_file(photo.file_id)
        file_path = file_info.file_path
        
        # 生成本地文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_filename = f"{timestamp}_{photo.file_id}.jpg"
        local_path = os.path.join(IMAGE_DIR, local_filename)
        
        # 下载并保存图片
        await msg.bot.download_file(file_path, local_path)
        
        await msg.answer(f"📷 图片已保存：{local_filename}")
        log_info("image.uploaded", filename=local_filename, user_id=msg.from_user.id if msg.from_user else 0)
        
    except Exception as e:
        await msg.answer(f"❌ 图片保存失败：{str(e)}")
        log_error("image.upload.failed", error=str(e))




async def setup_bot(dp: Dispatcher) -> None:
    """设置机器人"""
    # 初始化数据库
    await init_engine(settings.DATABASE_URL)
    
    # 启动网络健康检查器
    await network_health_checker.start()
    
    # 注册中间件
    dp.message.middleware(ErrorHandlingMiddleware())
    dp.callback_query.middleware(ErrorHandlingMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    
    # 注册路由器（每次都是新的Dispatcher实例，所以不会重复）
    dp.include_router(router)
    
    log_info("bot.setup.completed")

async def shutdown_bot() -> None:
    """关闭机器人时的清理工作"""
    # 停止网络健康检查器
    await network_health_checker.stop()
    
    # 关闭数据库连接
    from ..core.db import close_engine
    await close_engine()
    
    log_info("bot.shutdown.completed")
