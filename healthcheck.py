#!/usr/bin/env python3
"""
健康检查脚本
用于Docker容器健康检查，验证机器人服务是否正常运行
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径到Python路径
sys.path.insert(0, '/app')

async def health_check():
    """执行健康检查"""
    try:
        # 检查数据库文件是否存在且可访问
        db_path = Path('/app/data/orderbot.db')
        if not db_path.exists():
            print("数据库文件不存在")
            return False
            
        # 尝试导入核心模块
        from orderbot.src.config import Settings
        from orderbot.src.core.db import get_session
        
        # 检查配置是否正确加载
        settings = Settings()
        if not settings.BOT_TOKEN:
            print("BOT_TOKEN 未配置")
            return False
            
        # 尝试连接数据库
        async with get_session() as session:
            # 执行简单查询测试数据库连接
            result = await session.execute("SELECT 1")
            if not result.scalar():
                print("数据库连接失败")
                return False
                
        print("健康检查通过")
        return True
        
    except ImportError as e:
        print(f"模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False

def main():
    """主函数"""
    try:
        result = asyncio.run(health_check())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"健康检查异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()