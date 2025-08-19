#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进程监控和自动恢复模块
提供进程状态监控、自动重启和资源监控功能
"""

import asyncio
import logging
import os
import psutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessState(Enum):
    """进程状态枚举"""
    RUNNING = "running"
    STOPPED = "stopped"
    CRASHED = "crashed"
    RESTARTING = "restarting"
    FAILED = "failed"


@dataclass
class ProcessInfo:
    """进程信息"""
    pid: Optional[int] = None
    name: str = ""
    command: List[str] = field(default_factory=list)
    state: ProcessState = ProcessState.STOPPED
    start_time: Optional[datetime] = None
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "pid": self.pid,
            "name": self.name,
            "command": self.command,
            "state": self.state.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "restart_count": self.restart_count,
            "last_restart": self.last_restart.isoformat() if self.last_restart else None,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_mb": self.memory_mb
        }


@dataclass
class MonitorConfig:
    """监控配置"""
    check_interval: float = 30.0  # 检查间隔（秒）
    max_restarts: int = 5  # 最大重启次数
    restart_window: int = 300  # 重启窗口期（秒）
    cpu_threshold: float = 90.0  # CPU使用率阈值
    memory_threshold: float = 80.0  # 内存使用率阈值
    enable_auto_restart: bool = True  # 启用自动重启
    restart_delay: float = 5.0  # 重启延迟（秒）
    health_check_timeout: float = 10.0  # 健康检查超时
    log_file: Optional[str] = None  # 日志文件路径


class ProcessMonitor:
    """进程监控器"""
    
    def __init__(self, config: MonitorConfig = None):
        self.config = config or MonitorConfig()
        self.processes: Dict[str, ProcessInfo] = {}
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._health_callbacks: Dict[str, Callable] = {}
        self._alert_callbacks: List[Callable] = []
        
        # 设置日志
        if self.config.log_file:
            handler = logging.FileHandler(self.config.log_file)
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            logger.addHandler(handler)
    
    def register_process(self, name: str, command: List[str], 
                        health_check: Optional[Callable] = None) -> None:
        """注册要监控的进程"""
        self.processes[name] = ProcessInfo(
            name=name,
            command=command,
            state=ProcessState.STOPPED
        )
        
        if health_check:
            self._health_callbacks[name] = health_check
            
        logger.info(f"已注册进程监控: {name}")
    
    def add_alert_callback(self, callback: Callable) -> None:
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    async def start_monitoring(self) -> None:
        """开始监控"""
        if self.is_running:
            logger.warning("进程监控器已在运行")
            return
            
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("进程监控器已启动")
    
    async def stop_monitoring(self) -> None:
        """停止监控"""
        self.is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
                
        logger.info("进程监控器已停止")
    
    async def start_process(self, name: str) -> bool:
        """启动进程"""
        if name not in self.processes:
            logger.error(f"未找到进程配置: {name}")
            return False
            
        process_info = self.processes[name]
        
        if process_info.state == ProcessState.RUNNING:
            logger.warning(f"进程 {name} 已在运行")
            return True
            
        try:
            # 启动进程
            proc = await asyncio.create_subprocess_exec(
                *process_info.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            process_info.pid = proc.pid
            process_info.state = ProcessState.RUNNING
            process_info.start_time = datetime.now()
            
            logger.info(f"进程 {name} 已启动，PID: {proc.pid}")
            return True
            
        except Exception as e:
            logger.error(f"启动进程 {name} 失败: {e}")
            process_info.state = ProcessState.FAILED
            return False
    
    async def stop_process(self, name: str, force: bool = False) -> bool:
        """停止进程"""
        if name not in self.processes:
            logger.error(f"未找到进程配置: {name}")
            return False
            
        process_info = self.processes[name]
        
        if not process_info.pid:
            logger.warning(f"进程 {name} 未运行")
            return True
            
        try:
            process = psutil.Process(process_info.pid)
            
            if force:
                process.kill()
                logger.info(f"强制终止进程 {name}")
            else:
                process.terminate()
                logger.info(f"正常终止进程 {name}")
                
                # 等待进程结束
                try:
                    process.wait(timeout=10)
                except psutil.TimeoutExpired:
                    logger.warning(f"进程 {name} 未在10秒内结束，强制终止")
                    process.kill()
            
            process_info.pid = None
            process_info.state = ProcessState.STOPPED
            return True
            
        except psutil.NoSuchProcess:
            logger.info(f"进程 {name} 已不存在")
            process_info.pid = None
            process_info.state = ProcessState.STOPPED
            return True
        except Exception as e:
            logger.error(f"停止进程 {name} 失败: {e}")
            return False
    
    async def restart_process(self, name: str) -> bool:
        """重启进程"""
        logger.info(f"重启进程: {name}")
        
        # 停止进程
        await self.stop_process(name)
        
        # 等待重启延迟
        await asyncio.sleep(self.config.restart_delay)
        
        # 启动进程
        success = await self.start_process(name)
        
        if success:
            process_info = self.processes[name]
            process_info.restart_count += 1
            process_info.last_restart = datetime.now()
            
            # 发送告警
            await self._send_alert(f"进程 {name} 已重启，重启次数: {process_info.restart_count}")
            
        return success
    
    def get_process_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取进程状态"""
        if name not in self.processes:
            return None
            
        return self.processes[name].to_dict()
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有进程状态"""
        return {name: info.to_dict() for name, info in self.processes.items()}
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self.is_running:
            try:
                await self._check_processes()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(self.config.check_interval)
    
    async def _check_processes(self) -> None:
        """检查所有进程"""
        for name, process_info in self.processes.items():
            await self._check_single_process(name, process_info)
    
    async def _check_single_process(self, name: str, process_info: ProcessInfo) -> None:
        """检查单个进程"""
        try:
            # 检查进程是否存在
            if process_info.pid:
                try:
                    process = psutil.Process(process_info.pid)
                    
                    # 更新资源使用情况
                    process_info.cpu_percent = process.cpu_percent()
                    memory_info = process.memory_info()
                    process_info.memory_mb = memory_info.rss / 1024 / 1024
                    process_info.memory_percent = process.memory_percent()
                    
                    # 检查资源使用率
                    await self._check_resource_usage(name, process_info)
                    
                    # 执行健康检查
                    if name in self._health_callbacks:
                        try:
                            health_ok = await asyncio.wait_for(
                                self._health_callbacks[name](),
                                timeout=self.config.health_check_timeout
                            )
                            
                            if not health_ok:
                                logger.warning(f"进程 {name} 健康检查失败")
                                await self._handle_unhealthy_process(name, process_info)
                                
                        except asyncio.TimeoutError:
                            logger.warning(f"进程 {name} 健康检查超时")
                            await self._handle_unhealthy_process(name, process_info)
                        except Exception as e:
                            logger.error(f"进程 {name} 健康检查异常: {e}")
                    
                except psutil.NoSuchProcess:
                    logger.warning(f"进程 {name} (PID: {process_info.pid}) 已停止")
                    process_info.pid = None
                    process_info.state = ProcessState.CRASHED
                    
                    if self.config.enable_auto_restart:
                        await self._handle_crashed_process(name, process_info)
            
            elif process_info.state == ProcessState.RUNNING:
                # 进程应该在运行但PID为空
                process_info.state = ProcessState.CRASHED
                if self.config.enable_auto_restart:
                    await self._handle_crashed_process(name, process_info)
                    
        except Exception as e:
            logger.error(f"检查进程 {name} 时发生异常: {e}")
    
    async def _check_resource_usage(self, name: str, process_info: ProcessInfo) -> None:
        """检查资源使用情况"""
        # CPU使用率检查
        if process_info.cpu_percent > self.config.cpu_threshold:
            await self._send_alert(
                f"进程 {name} CPU使用率过高: {process_info.cpu_percent:.1f}%"
            )
        
        # 内存使用率检查
        if process_info.memory_percent > self.config.memory_threshold:
            await self._send_alert(
                f"进程 {name} 内存使用率过高: {process_info.memory_percent:.1f}% ({process_info.memory_mb:.1f}MB)"
            )
    
    async def _handle_crashed_process(self, name: str, process_info: ProcessInfo) -> None:
        """处理崩溃的进程"""
        # 检查重启次数限制
        if not self._can_restart(process_info):
            logger.error(f"进程 {name} 重启次数超限，停止自动重启")
            process_info.state = ProcessState.FAILED
            await self._send_alert(f"进程 {name} 重启次数超限，已停止自动重启")
            return
        
        logger.info(f"尝试重启崩溃的进程: {name}")
        process_info.state = ProcessState.RESTARTING
        
        success = await self.restart_process(name)
        if not success:
            process_info.state = ProcessState.FAILED
            await self._send_alert(f"进程 {name} 重启失败")
    
    async def _handle_unhealthy_process(self, name: str, process_info: ProcessInfo) -> None:
        """处理不健康的进程"""
        if self.config.enable_auto_restart and self._can_restart(process_info):
            logger.info(f"重启不健康的进程: {name}")
            await self.restart_process(name)
        else:
            await self._send_alert(f"进程 {name} 健康检查失败但未重启")
    
    def _can_restart(self, process_info: ProcessInfo) -> bool:
        """检查是否可以重启"""
        if process_info.restart_count >= self.config.max_restarts:
            return False
        
        # 检查重启窗口期
        if process_info.last_restart:
            time_since_restart = datetime.now() - process_info.last_restart
            if time_since_restart.total_seconds() < self.config.restart_window:
                return process_info.restart_count < self.config.max_restarts
            else:
                # 重置重启计数器
                process_info.restart_count = 0
        
        return True
    
    async def _send_alert(self, message: str) -> None:
        """发送告警"""
        logger.warning(f"告警: {message}")
        
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"发送告警失败: {e}")


# 全局进程监控器实例
process_monitor = ProcessMonitor()


async def setup_bot_monitoring(bot_command: List[str], 
                              health_check_func: Optional[Callable] = None) -> None:
    """设置机器人监控"""
    # 注册机器人进程
    process_monitor.register_process(
        "telegram_bot",
        bot_command,
        health_check_func
    )
    
    # 启动监控
    await process_monitor.start_monitoring()
    logger.info("机器人进程监控已设置")


async def shutdown_monitoring() -> None:
    """关闭监控"""
    await process_monitor.stop_monitoring()
    logger.info("进程监控已关闭")