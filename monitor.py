#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统监控脚本
监控机器人服务状态、系统资源使用情况，并提供告警功能
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from orderbot.src.utils.process_monitor import ProcessMonitor, MonitorConfig, ProcessState
    from orderbot.src.utils.network import NetworkHealthChecker, check_network_connectivity
    from orderbot.src.core.database import health_check as db_health_check
    from orderbot.src.core.settings import Settings
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self):
        self.settings = Settings()
        self.process_monitor = ProcessMonitor(
            MonitorConfig(
                check_interval=30.0,
                max_restarts=5,
                restart_window=300,
                cpu_threshold=80.0,
                memory_threshold=70.0,
                enable_auto_restart=True,
                log_file='logs/process_monitor.log'
            )
        )
        self.network_checker = NetworkHealthChecker(check_interval=60.0)
        self.is_running = False
        self.start_time = datetime.now()
        self.stats = {
            'total_checks': 0,
            'failed_checks': 0,
            'restarts': 0,
            'alerts_sent': 0
        }
        
        # 设置告警回调
        self.process_monitor.add_alert_callback(self._handle_alert)
    
    async def start(self) -> None:
        """启动系统监控"""
        if self.is_running:
            logger.warning("系统监控已在运行")
            return
        
        logger.info("启动系统监控...")
        self.is_running = True
        
        try:
            # 注册机器人进程
            bot_command = [sys.executable, "app.py"]
            self.process_monitor.register_process(
                "telegram_bot",
                bot_command,
                self._bot_health_check
            )
            
            # 启动各个监控组件
            await self.process_monitor.start_monitoring()
            await self.network_checker.start()
            
            # 启动机器人进程
            await self.process_monitor.start_process("telegram_bot")
            
            logger.info("系统监控启动完成")
            
            # 开始监控循环
            await self._monitor_loop()
            
        except Exception as e:
            logger.error(f"启动系统监控失败: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """停止系统监控"""
        if not self.is_running:
            return
        
        logger.info("停止系统监控...")
        self.is_running = False
        
        try:
            # 停止监控组件
            await self.process_monitor.stop_monitoring()
            await self.network_checker.stop()
            
            # 生成监控报告
            await self._generate_report()
            
            logger.info("系统监控已停止")
            
        except Exception as e:
            logger.error(f"停止系统监控时发生错误: {e}")
    
    async def _monitor_loop(self) -> None:
        """主监控循环"""
        while self.is_running:
            try:
                await self._perform_system_check()
                await asyncio.sleep(60)  # 每分钟检查一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(60)
    
    async def _perform_system_check(self) -> None:
        """执行系统检查"""
        self.stats['total_checks'] += 1
        check_results = {}
        
        try:
            # 检查数据库连接
            db_healthy = await self._check_database()
            check_results['database'] = db_healthy
            
            # 检查网络连接
            network_healthy = await self._check_network()
            check_results['network'] = network_healthy
            
            # 检查进程状态
            process_healthy = await self._check_processes()
            check_results['processes'] = process_healthy
            
            # 检查系统资源
            resource_healthy = await self._check_system_resources()
            check_results['resources'] = resource_healthy
            
            # 检查磁盘空间
            disk_healthy = await self._check_disk_space()
            check_results['disk'] = disk_healthy
            
            # 统计检查结果
            failed_checks = sum(1 for result in check_results.values() if not result)
            if failed_checks > 0:
                self.stats['failed_checks'] += 1
                logger.warning(f"系统检查发现 {failed_checks} 个问题")
            
            # 记录检查结果
            await self._log_check_results(check_results)
            
        except Exception as e:
            logger.error(f"系统检查异常: {e}")
            self.stats['failed_checks'] += 1
    
    async def _check_database(self) -> bool:
        """检查数据库连接"""
        try:
            result = await db_health_check()
            if not result:
                await self._handle_alert("数据库连接检查失败")
            return result
        except Exception as e:
            logger.error(f"数据库检查异常: {e}")
            await self._handle_alert(f"数据库检查异常: {e}")
            return False
    
    async def _check_network(self) -> bool:
        """检查网络连接"""
        try:
            network_status = self.network_checker.get_status()
            if not network_status['is_healthy']:
                await self._handle_alert("网络连接异常")
            return network_status['is_healthy']
        except Exception as e:
            logger.error(f"网络检查异常: {e}")
            return False
    
    async def _check_processes(self) -> bool:
        """检查进程状态"""
        try:
            all_status = self.process_monitor.get_all_status()
            healthy = True
            
            for name, status in all_status.items():
                if status['state'] in [ProcessState.CRASHED.value, ProcessState.FAILED.value]:
                    healthy = False
                    await self._handle_alert(f"进程 {name} 状态异常: {status['state']}")
            
            return healthy
        except Exception as e:
            logger.error(f"进程检查异常: {e}")
            return False
    
    async def _check_system_resources(self) -> bool:
        """检查系统资源"""
        try:
            import psutil
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                await self._handle_alert(f"系统CPU使用率过高: {cpu_percent:.1f}%")
                return False
            
            # 内存使用率
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                await self._handle_alert(f"系统内存使用率过高: {memory.percent:.1f}%")
                return False
            
            # 负载平均值（仅Linux/macOS）
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()[0]
                cpu_count = psutil.cpu_count()
                if load_avg > cpu_count * 2:
                    await self._handle_alert(f"系统负载过高: {load_avg:.2f}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"系统资源检查异常: {e}")
            return False
    
    async def _check_disk_space(self) -> bool:
        """检查磁盘空间"""
        try:
            import psutil
            
            # 检查当前目录所在磁盘
            disk_usage = psutil.disk_usage('.')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            
            if free_percent < 10:  # 剩余空间少于10%
                await self._handle_alert(
                    f"磁盘空间不足: 剩余 {free_percent:.1f}% "
                    f"({disk_usage.free / 1024**3:.1f}GB)"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"磁盘空间检查异常: {e}")
            return False
    
    async def _bot_health_check(self) -> bool:
        """机器人健康检查"""
        try:
            # 检查日志文件是否有最近的活动
            log_file = Path('logs/bot.log')
            if log_file.exists():
                # 检查最近5分钟内是否有日志更新
                last_modified = datetime.fromtimestamp(log_file.stat().st_mtime)
                if datetime.now() - last_modified > timedelta(minutes=5):
                    logger.warning("机器人日志文件长时间未更新")
                    return False
            
            # 可以添加更多健康检查逻辑
            # 例如：检查Telegram API连接、检查数据库操作等
            
            return True
            
        except Exception as e:
            logger.error(f"机器人健康检查异常: {e}")
            return False
    
    async def _handle_alert(self, message: str) -> None:
        """处理告警"""
        self.stats['alerts_sent'] += 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        alert_message = f"[{timestamp}] 系统告警: {message}"
        
        # 记录到日志
        logger.warning(alert_message)
        
        # 写入告警文件
        alert_file = Path('logs/alerts.log')
        alert_file.parent.mkdir(exist_ok=True)
        
        with open(alert_file, 'a', encoding='utf-8') as f:
            f.write(f"{alert_message}\n")
        
        # 这里可以添加其他告警方式，如发送邮件、Webhook等
        # await self._send_webhook_alert(alert_message)
    
    async def _log_check_results(self, results: Dict[str, bool]) -> None:
        """记录检查结果"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'stats': self.stats.copy()
        }
        
        # 写入检查结果文件
        results_file = Path('logs/check_results.jsonl')
        results_file.parent.mkdir(exist_ok=True)
        
        with open(results_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    async def _generate_report(self) -> None:
        """生成监控报告"""
        uptime = datetime.now() - self.start_time
        
        report = {
            'monitoring_period': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'uptime_seconds': uptime.total_seconds(),
                'uptime_formatted': str(uptime)
            },
            'statistics': self.stats,
            'process_status': self.process_monitor.get_all_status(),
            'network_status': self.network_checker.get_status()
        }
        
        # 保存报告
        report_file = Path(f'logs/monitor_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        report_file.parent.mkdir(exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"监控报告已保存: {report_file}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        uptime = datetime.now() - self.start_time
        
        return {
            'is_running': self.is_running,
            'uptime_seconds': uptime.total_seconds(),
            'statistics': self.stats,
            'process_status': self.process_monitor.get_all_status(),
            'network_status': self.network_checker.get_status()
        }


async def main():
    """主函数"""
    import signal
    
    # 创建日志目录
    Path('logs').mkdir(exist_ok=True)
    
    monitor = SystemMonitor()
    
    # 设置信号处理
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，准备停止监控...")
        asyncio.create_task(monitor.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止监控...")
    except Exception as e:
        logger.error(f"监控运行异常: {e}")
    finally:
        await monitor.stop()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"监控启动失败: {e}")
        sys.exit(1)