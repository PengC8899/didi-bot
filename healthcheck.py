#!/usr/bin/env python3

import os
import sys
import sqlite3
import asyncio
import aiohttp
import time
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "orderbot" / "src"))

try:
    from config import Settings
    from core.db import init_engine, get_session, health_check as db_health_check
    from utils.network import check_network_connectivity, network_monitor
except ImportError as e:
    print(f"❌ 无法导入配置: {e}")
    sys.exit(1)

class HealthChecker:
    """综合健康检查器"""
    
    def __init__(self):
        self.settings = Settings()
        self.results: Dict[str, Dict[str, Any]] = {}
        
    def record_check(self, name: str, passed: bool, message: str, details: Optional[Dict] = None):
        """记录检查结果"""
        self.results[name] = {
            "passed": passed,
            "message": message,
            "details": details or {},
            "timestamp": time.time()
        }
        
        status = "✅" if passed else "❌"
        print(f"{status} {name}: {message}")
        
        if details:
            for key, value in details.items():
                print(f"   {key}: {value}")
    
    def check_environment(self):
        """检查环境变量"""
        required_vars = {
            "BOT_TOKEN": self.settings.BOT_TOKEN,
            "DATABASE_URL": self.settings.DATABASE_URL,
        }
        
        optional_vars = {
            "CHANNEL_ID": self.settings.CHANNEL_ID,
            "OPERATOR_USER_ID": self.settings.OPERATOR_USER_ID,
            "LOG_LEVEL": self.settings.LOG_LEVEL,
        }
        
        missing_required = []
        for var_name, value in required_vars.items():
            if not value:
                missing_required.append(var_name)
        
        if missing_required:
            self.record_check(
                "环境变量",
                False,
                f"缺少必需的环境变量: {', '.join(missing_required)}",
                {"missing": missing_required}
            )
            return False
        
        # 检查BOT_TOKEN格式
        if len(self.settings.BOT_TOKEN) < 10 or ":" not in self.settings.BOT_TOKEN:
            self.record_check(
                "环境变量",
                False,
                "BOT_TOKEN 格式不正确",
                {"token_length": len(self.settings.BOT_TOKEN)}
            )
            return False
        
        details = {
            "required_vars": list(required_vars.keys()),
            "optional_vars_set": [k for k, v in optional_vars.items() if v]
        }
        
        self.record_check(
            "环境变量",
            True,
            "所有必需的环境变量已设置",
            details
        )
        return True
    
    def check_database_file(self):
        """检查数据库文件"""
        db_path = self.settings.DATABASE_URL.replace("sqlite:///", "")
        
        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            self.record_check(
                "数据库文件",
                False,
                f"数据库文件不存在: {db_path}"
            )
            return False
        
        # 检查数据库文件权限
        if not os.access(db_path, os.R_OK | os.W_OK):
            self.record_check(
                "数据库文件",
                False,
                f"数据库文件权限不足: {db_path}"
            )
            return False
        
        # 获取文件信息
        stat = os.stat(db_path)
        details = {
            "path": db_path,
            "size_bytes": stat.st_size,
            "modified": time.ctime(stat.st_mtime)
        }
        
        self.record_check(
            "数据库文件",
            True,
            "数据库文件存在且可访问",
            details
        )
        return True
    
    async def check_database_connection(self):
        """检查数据库连接"""
        try:
            # 初始化数据库引擎
            await init_engine(self.settings.DATABASE_URL)
            
            # 执行健康检查
            is_healthy = await db_health_check()
            
            if is_healthy:
                self.record_check(
                    "数据库连接",
                    True,
                    "数据库连接正常"
                )
                return True
            else:
                self.record_check(
                    "数据库连接",
                    False,
                    "数据库健康检查失败"
                )
                return False
                
        except Exception as e:
            self.record_check(
                "数据库连接",
                False,
                f"数据库连接失败: {str(e)}"
            )
            return False
    
    async def check_network_connectivity_async(self):
        """检查网络连接"""
        try:
            is_connected = await check_network_connectivity(timeout=10.0)
            
            if is_connected:
                self.record_check(
                    "网络连接",
                    True,
                    "网络连接正常"
                )
                return True
            else:
                self.record_check(
                    "网络连接",
                    False,
                    "网络连接异常"
                )
                return False
                
        except Exception as e:
            self.record_check(
                "网络连接",
                False,
                f"网络连接检查失败: {str(e)}"
            )
            return False
    
    async def check_telegram_api(self):
        """检查Telegram API连接"""
        try:
            url = f"https://api.telegram.org/bot{self.settings.BOT_TOKEN}/getMe"
            
            timeout = aiohttp.ClientTimeout(total=10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            bot_info = data.get("result", {})
                            details = {
                                "bot_username": bot_info.get("username"),
                                "bot_name": bot_info.get("first_name"),
                                "can_join_groups": bot_info.get("can_join_groups"),
                                "can_read_all_group_messages": bot_info.get("can_read_all_group_messages")
                            }
                            
                            self.record_check(
                                "Telegram API",
                                True,
                                "Telegram API连接正常",
                                details
                            )
                            return True
                    
                    self.record_check(
                        "Telegram API",
                        False,
                        f"Telegram API响应异常: HTTP {response.status}"
                    )
                    return False
                    
        except Exception as e:
            self.record_check(
                "Telegram API",
                False,
                f"Telegram API连接失败: {str(e)}"
            )
            return False
    
    def check_file_permissions(self):
        """检查文件权限"""
        paths_to_check = [
            ("./data", "数据目录"),
            ("./images", "图片目录"),
            ("./logs", "日志目录"),
        ]
        
        issues = []
        
        for path, description in paths_to_check:
            if os.path.exists(path):
                if not os.access(path, os.R_OK | os.W_OK):
                    issues.append(f"{description}权限不足")
            else:
                try:
                    os.makedirs(path, exist_ok=True)
                except Exception as e:
                    issues.append(f"无法创建{description}: {str(e)}")
        
        if issues:
            self.record_check(
                "文件权限",
                False,
                "文件权限检查失败",
                {"issues": issues}
            )
            return False
        
        self.record_check(
            "文件权限",
            True,
            "文件权限正常"
        )
        return True
    
    def get_system_info(self):
        """获取系统信息"""
        import platform
        import psutil
        
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            details = {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "memory_percent": memory.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "disk_percent": round((disk.used / disk.total) * 100, 1)
            }
            
            self.record_check(
                "系统信息",
                True,
                "系统信息收集完成",
                details
            )
            return True
            
        except Exception as e:
            self.record_check(
                "系统信息",
                False,
                f"系统信息收集失败: {str(e)}"
            )
            return False
    
    async def run_all_checks(self):
        """运行所有健康检查"""
        print("🔍 开始综合健康检查...\n")
        
        checks = [
            ("环境变量检查", self.check_environment, False),
            ("文件权限检查", self.check_file_permissions, False),
            ("数据库文件检查", self.check_database_file, False),
            ("数据库连接检查", self.check_database_connection, True),
            ("网络连接检查", self.check_network_connectivity_async, True),
            ("Telegram API检查", self.check_telegram_api, True),
            ("系统信息收集", self.get_system_info, False),
        ]
        
        passed_count = 0
        total_count = len(checks)
        
        for name, check_func, is_async in checks:
            print(f"\n📋 {name}:")
            try:
                if is_async:
                    result = await check_func()
                else:
                    result = check_func()
                    
                if result:
                    passed_count += 1
                    
            except Exception as e:
                print(f"❌ {name}执行失败: {str(e)}")
        
        print("\n" + "="*60)
        print(f"📊 健康检查结果: {passed_count}/{total_count} 通过")
        
        if passed_count == total_count:
            print("✅ 所有健康检查通过，系统状态良好")
            return True
        else:
            print(f"❌ {total_count - passed_count} 项检查失败，需要注意")
            return False
    
    def get_summary(self):
        """获取检查摘要"""
        return {
            "total_checks": len(self.results),
            "passed_checks": sum(1 for r in self.results.values() if r["passed"]),
            "failed_checks": sum(1 for r in self.results.values() if not r["passed"]),
            "results": self.results
        }

async def main():
    """主健康检查函数"""
    checker = HealthChecker()
    
    try:
        success = await checker.run_all_checks()
        
        # 输出详细摘要
        summary = checker.get_summary()
        print(f"\n📈 检查摘要:")
        print(f"   总检查项: {summary['total_checks']}")
        print(f"   通过: {summary['passed_checks']}")
        print(f"   失败: {summary['failed_checks']}")
        
        if success:
            print("\n🎉 健康检查完成，系统运行正常！")
            sys.exit(0)
        else:
            print("\n⚠️  健康检查发现问题，请检查上述失败项！")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  健康检查被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 健康检查执行异常: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # 安装必要的依赖检查
    try:
        import psutil
    except ImportError:
        print("❌ 缺少psutil依赖，请运行: pip install psutil")
        sys.exit(1)
    
    asyncio.run(main())