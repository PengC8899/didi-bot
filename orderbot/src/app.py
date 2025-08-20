import asyncio
import logging
import os
import signal
import sys
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientTimeout

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有安装 python-dotenv，跳过
    pass

from .config import Settings
from .tg.bot import setup_bot, shutdown_bot
from .utils.logging import log_info, log_error
from .utils.process_monitor import setup_bot_monitoring, shutdown_monitoring, MonitorConfig

# 全局变量用于优雅关闭
bot_instance: Optional[Bot] = None
dp_instance: Optional[Dispatcher] = None
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """信号处理器"""
    log_info("signal.received", signal=signum)
    shutdown_event.set()

async def create_bot(settings: Settings) -> Bot:
    """创建Bot实例，配置网络超时和重试"""
    # 配置HTTP会话，设置超时和重试
    timeout = ClientTimeout(
        total=30,  # 总超时时间
        connect=10,  # 连接超时
        sock_read=20  # 读取超时
    )
    
    session = AiohttpSession(
        timeout=timeout,
        connector_kwargs={
            'limit': 100,  # 连接池大小
            'limit_per_host': 30,  # 每个主机的连接数
            'ttl_dns_cache': 300,  # DNS缓存时间
            'use_dns_cache': True,
        }
    )
    
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session
    )
    
    return bot

async def run_bot_with_restart(settings: Settings):
    """运行机器人，支持自动重启"""
    max_retries = 5
    retry_count = 0
    base_delay = 5  # 基础重试延迟（秒）
    
    while retry_count < max_retries and not shutdown_event.is_set():
        try:
            # 创建Bot实例
            global bot_instance, dp_instance
            bot_instance = await create_bot(settings)
            
            # 创建Dispatcher实例
            dp_instance = Dispatcher()
            
            # 设置机器人
            await setup_bot(dp_instance)
            
            # 重置重试计数器
            retry_count = 0
            
            # 开始轮询
            log_info("bot.polling.start")
            await dp_instance.start_polling(
                bot_instance,
                handle_signals=False,  # 我们自己处理信号
                allowed_updates=['message', 'callback_query', 'inline_query']
            )
            
        except asyncio.CancelledError:
            log_info("bot.polling.cancelled")
            break
        except Exception as e:
            retry_count += 1
            delay = min(base_delay * (2 ** (retry_count - 1)), 300)  # 指数退避，最大5分钟
            
            log_error("bot.polling.error", error=str(e), retry_count=retry_count, max_retries=max_retries)
            
            if retry_count >= max_retries:
                log_error("bot.max_retries_reached")
                break
            
            log_info("bot.retry_delay", delay=delay)
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
                break  # 如果在等待期间收到关闭信号，则退出
            except asyncio.TimeoutError:
                continue  # 超时后继续重试
        finally:
            # 清理资源
            if dp_instance:
                try:
                    await shutdown_bot()
                except Exception as e:
                    log_error("bot.shutdown_error", error=str(e))
            if bot_instance:
                try:
                    await bot_instance.session.close()
                except Exception as e:
                    log_error("bot.session.close_error", error=str(e))
                bot_instance = None
            dp_instance = None

async def main() -> None:
    """Application entrypoint: start long polling bot."""
    settings = Settings()  # loads from env

    # Configure basic logging early
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 确保日志目录存在
    os.makedirs('logs', exist_ok=True)
    
    # 初始化进程监控器
    monitor_config = MonitorConfig(
        check_interval=30,  # 30秒检查一次
        cpu_threshold=80.0,  # CPU使用率阈值
        memory_threshold=80.0,  # 内存使用率阈值
        max_restarts=5,  # 最大重启次数
        restart_window=3600  # 重启窗口期（1小时）
    )
    await setup_bot_monitoring([], None)
    log_info("process.monitor.initialized")
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await run_bot_with_restart(settings)
    except KeyboardInterrupt:
        log_info("bot.keyboard_interrupt")
    except Exception as e:
        log_error("bot.main_error", error=str(e))
        sys.exit(1)
    finally:
        log_info("bot.shutdown")
        # 关闭进程监控器
        try:
            await shutdown_monitoring()
            log_info("process.monitor.shutdown")
        except Exception as e:
            log_error("process.monitor.shutdown_error", error=str(e))
        
        # 确保资源被清理
        if dp_instance:
            try:
                await shutdown_bot()
            except Exception as e:
                log_error("bot.final_shutdown_error", error=str(e))
        if bot_instance:
            try:
                await bot_instance.session.close()
            except Exception as e:
                log_error("bot.final_cleanup_error", error=str(e))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log_info("bot.interrupted_by_user")
    except Exception as e:
        log_error("bot.startup_error", error=str(e))
        sys.exit(1)
