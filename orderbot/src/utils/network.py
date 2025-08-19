import asyncio
import logging
import time
from typing import Optional, Callable, Any
from aiohttp import ClientSession, ClientTimeout, ClientError
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramServerError

logger = logging.getLogger(__name__)

class NetworkMonitor:
    """网络连接监控和重试机制"""
    
    def __init__(self):
        self.connection_failures = 0
        self.last_failure_time = 0
        self.max_failures = 5
        self.failure_window = 300  # 5分钟窗口
        
    def record_failure(self):
        """记录网络失败"""
        current_time = time.time()
        
        # 如果超过窗口时间，重置计数器
        if current_time - self.last_failure_time > self.failure_window:
            self.connection_failures = 0
            
        self.connection_failures += 1
        self.last_failure_time = current_time
        
        logger.warning(f"网络连接失败，当前失败次数: {self.connection_failures}")
        
    def record_success(self):
        """记录网络成功"""
        if self.connection_failures > 0:
            logger.info("网络连接恢复正常")
            self.connection_failures = 0
            
    def is_network_healthy(self) -> bool:
        """检查网络是否健康"""
        current_time = time.time()
        
        # 如果超过窗口时间，认为网络已恢复
        if current_time - self.last_failure_time > self.failure_window:
            self.connection_failures = 0
            return True
            
        return self.connection_failures < self.max_failures
        
    def get_backoff_delay(self) -> float:
        """获取退避延迟时间"""
        if self.connection_failures == 0:
            return 0
            
        # 指数退避，最大60秒
        delay = min(2 ** (self.connection_failures - 1), 60)
        return delay

class RetryConfig:
    """重试配置"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        
    def get_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if attempt <= 0:
            return 0
            
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # 添加50%的随机抖动
            
        return delay

async def retry_with_backoff(
    func: Callable,
    *args,
    retry_config: Optional[RetryConfig] = None,
    network_monitor: Optional[NetworkMonitor] = None,
    **kwargs
) -> Any:
    """带退避的重试装饰器"""
    if retry_config is None:
        retry_config = RetryConfig()
        
    last_exception = None
    
    for attempt in range(retry_config.max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            
            # 记录成功
            if network_monitor:
                network_monitor.record_success()
                
            return result
            
        except (TelegramNetworkError, ClientError, asyncio.TimeoutError) as e:
            last_exception = e
            
            # 记录失败
            if network_monitor:
                network_monitor.record_failure()
                
            if attempt < retry_config.max_retries:
                delay = retry_config.get_delay(attempt + 1)
                logger.warning(
                    f"网络操作失败 (尝试 {attempt + 1}/{retry_config.max_retries + 1}): {e}. "
                    f"将在 {delay:.2f} 秒后重试"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"网络操作最终失败，已达到最大重试次数: {e}")
                
        except TelegramRetryAfter as e:
            # Telegram API 限流
            if attempt < retry_config.max_retries:
                delay = e.retry_after + 1  # 额外等待1秒
                logger.warning(
                    f"Telegram API 限流 (尝试 {attempt + 1}/{retry_config.max_retries + 1}): "
                    f"需要等待 {delay} 秒"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Telegram API 限流，已达到最大重试次数")
                last_exception = e
                
        except Exception as e:
            # 其他异常不重试
            logger.error(f"非网络异常，不进行重试: {e}")
            last_exception = e
            break
            
    raise last_exception

async def check_network_connectivity(timeout: float = 10.0) -> bool:
    """检查网络连接性"""
    test_urls = [
        "https://api.telegram.org",
        "https://www.google.com",
        "https://www.baidu.com"
    ]
    
    timeout_config = ClientTimeout(total=timeout)
    
    async with ClientSession(timeout=timeout_config) as session:
        for url in test_urls:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        logger.debug(f"网络连接正常: {url}")
                        return True
            except Exception as e:
                logger.debug(f"无法连接到 {url}: {e}")
                continue
                
    logger.warning("所有网络连接测试都失败")
    return False

class NetworkHealthChecker:
    """网络健康检查器"""
    
    def __init__(self, check_interval: float = 60.0):
        self.check_interval = check_interval
        self.is_running = False
        self.last_check_time = 0
        self.is_healthy = True
        self._task: Optional[asyncio.Task] = None
        
    async def start(self):
        """启动健康检查"""
        if self.is_running:
            return
            
        self.is_running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info("网络健康检查器已启动")
        
    async def stop(self):
        """停止健康检查"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("网络健康检查器已停止")
        
    async def _check_loop(self):
        """健康检查循环"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # 执行网络连接检查
                is_healthy = await check_network_connectivity()
                
                if is_healthy != self.is_healthy:
                    if is_healthy:
                        logger.info("网络连接已恢复")
                    else:
                        logger.warning("网络连接异常")
                        
                self.is_healthy = is_healthy
                self.last_check_time = current_time
                
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"网络健康检查异常: {e}")
                await asyncio.sleep(self.check_interval)
                
    def get_status(self) -> dict:
        """获取网络状态"""
        return {
            "is_healthy": self.is_healthy,
            "last_check_time": self.last_check_time,
            "is_running": self.is_running
        }

# 全局网络监控实例
network_monitor = NetworkMonitor()
network_health_checker = NetworkHealthChecker()

# 默认重试配置
default_retry_config = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)