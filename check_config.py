#!/usr/bin/env python3
"""
配置检查和验证脚本
用于诊断和修复常见的配置问题
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_status(message: str, status: bool, details: str = ""):
    """打印状态信息"""
    icon = f"{Colors.GREEN}✅{Colors.ENDC}" if status else f"{Colors.RED}❌{Colors.ENDC}"
    print(f"{icon} {message}")
    if details:
        print(f"   {Colors.YELLOW}→{Colors.ENDC} {details}")

def print_header(title: str):
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== {title} ==={Colors.ENDC}")

def load_env_file() -> Dict[str, str]:
    """加载 .env 文件"""
    env_vars = {}
    env_file = Path('.env')
    
    if not env_file.exists():
        return env_vars
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # 移除引号
                    value = value.strip('"\'')
                    env_vars[key] = value
    except Exception as e:
        print(f"{Colors.RED}读取 .env 文件失败: {e}{Colors.ENDC}")
    
    return env_vars

def check_basic_files() -> List[Tuple[str, bool, str]]:
    """检查基本文件"""
    results = []
    
    files_to_check = [
        ('.env', '环境配置文件'),
        ('deploy.sh', '部署脚本'),
        ('Dockerfile', 'Docker 配置文件'),
        ('docker-compose.yaml', 'Docker Compose 开发配置'),
        ('docker-compose.prod.yaml', 'Docker Compose 生产配置'),
        ('healthcheck.py', '健康检查脚本'),
    ]
    
    for filename, description in files_to_check:
        path = Path(filename)
        exists = path.exists()
        details = description if exists else f"缺少 {description}"
        results.append((filename, exists, details))
    
    return results

def check_file_permissions() -> List[Tuple[str, bool, str]]:
    """检查文件权限"""
    results = []
    
    executable_files = ['deploy.sh', 'healthcheck.py']
    
    for filename in executable_files:
        path = Path(filename)
        if path.exists():
            import stat
            mode = path.stat().st_mode
            executable = bool(mode & stat.S_IXUSR)
            details = "有执行权限" if executable else "缺少执行权限，运行: chmod +x " + filename
            results.append((filename, executable, details))
        else:
            results.append((filename, False, "文件不存在"))
    
    return results

def check_env_config(env_vars: Dict[str, str]) -> List[Tuple[str, bool, str]]:
    """检查环境变量配置"""
    results = []
    
    # 必需配置项
    required_configs = [
        ('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN', '机器人令牌'),
        ('BOT_USERNAME', 'your_bot_username', '机器人用户名'),
        ('CHANNEL_ID', '-1001234567890', '频道ID'),
    ]
    
    for key, default_value, description in required_configs:
        value = env_vars.get(key, '')
        is_configured = value and value != default_value
        
        if is_configured:
            details = f"{description} 已配置"
        else:
            details = f"{description} 未配置或使用默认值，请设置真实值"
        
        results.append((key, is_configured, details))
    
    # 可选配置项
    optional_configs = [
        ('OPERATOR_USER_ID', '运营人员用户ID'),
        ('OPERATOR_USERNAME', '运营人员用户名'),
        ('ALLOWED_ADMIN_IDS', '管理员ID列表'),
        ('ALLOWED_USER_IDS', '用户白名单（兼容历史）'),
        ('ALLOW_ANYONE_APPLY', '是否允许任何人申请'),
    ]
    
    for key, description in optional_configs:
        value = env_vars.get(key, '')
        is_configured = bool(value.strip())
        
        details = f"{description} {'已配置' if is_configured else '未配置（可选）'}"
        results.append((key, True, details))  # 可选项总是显示为通过
    
    return results

async def check_bot_connection(env_vars: Dict[str, str]) -> Tuple[bool, str]:
    """检查机器人连接"""
    bot_token = env_vars.get('BOT_TOKEN', '')
    
    if not bot_token or bot_token == 'YOUR_TELEGRAM_BOT_TOKEN':
        return False, "BOT_TOKEN 未配置或为默认值"
    
    try:
        # 尝试导入并测试连接
        from aiogram import Bot
        
        bot = Bot(token=bot_token)
        me = await bot.get_me()
        await bot.session.close()
        
        return True, f"机器人连接成功: @{me.username} ({me.first_name})"
    
    except ImportError:
        return False, "aiogram 库未安装，请运行: pip install aiogram"
    except Exception as e:
        return False, f"连接失败: {str(e)}"

def check_database_file() -> Tuple[bool, str]:
    """检查数据库文件"""
    db_files = ['orderbot.db', 'data/orderbot.db']
    
    for db_file in db_files:
        path = Path(db_file)
        if path.exists():
            size = path.stat().st_size
            return True, f"数据库文件存在: {db_file} ({size} bytes)"
    
    return False, "数据库文件不存在，首次运行时会自动创建"

def generate_fix_script(env_vars: Dict[str, str]) -> str:
    """生成修复脚本"""
    script_lines = [
        "#!/bin/bash",
        "# 自动生成的配置修复脚本",
        "echo '开始修复配置问题...'",
        ""
    ]
    
    # 检查并修复文件权限
    for filename in ['deploy.sh', 'healthcheck.py']:
        if Path(filename).exists():
            script_lines.append(f"chmod +x {filename}")
            script_lines.append(f"echo '✅ 已添加 {filename} 执行权限'")
    
    # 检查配置问题
    bot_token = env_vars.get('BOT_TOKEN', '')
    if not bot_token or bot_token == 'YOUR_TELEGRAM_BOT_TOKEN':
        script_lines.extend([
            "",
            "echo '❌ 请手动设置 BOT_TOKEN:'",
            "echo '1. 联系 @BotFather 获取机器人令牌'",
            "echo '2. 编辑 .env 文件，替换 BOT_TOKEN 值'",
            "echo '3. 重新运行此检查脚本'",
        ])
    
    script_lines.extend([
        "",
        "echo '修复脚本执行完成'",
        "echo '请检查上述输出并手动完成剩余配置'"
    ])
    
    return "\n".join(script_lines)

async def main():
    """主函数"""
    print(f"{Colors.BOLD}{Colors.BLUE}Telegram 订单机器人配置检查工具{Colors.ENDC}")
    print(f"当前目录: {Path.cwd()}")
    
    # 加载环境变量
    env_vars = load_env_file()
    
    # 检查基本文件
    print_header("文件检查")
    file_results = check_basic_files()
    for filename, status, details in file_results:
        print_status(filename, status, details)
    
    # 检查文件权限
    print_header("权限检查")
    perm_results = check_file_permissions()
    for filename, status, details in perm_results:
        print_status(filename, status, details)
    
    # 检查环境配置
    print_header("环境配置检查")
    if env_vars:
        config_results = check_env_config(env_vars)
        for key, status, details in config_results:
            print_status(key, status, details)
    else:
        print_status(".env 文件", False, "文件不存在或为空")
    
    # 检查机器人连接
    print_header("机器人连接检查")
    try:
        bot_status, bot_details = await check_bot_connection(env_vars)
        print_status("机器人连接", bot_status, bot_details)
    except Exception as e:
        print_status("机器人连接", False, f"检查失败: {e}")
    
    # 检查数据库
    print_header("数据库检查")
    db_status, db_details = check_database_file()
    print_status("数据库文件", db_status, db_details)
    
    # 生成修复建议
    print_header("修复建议")
    
    # 统计问题
    all_results = file_results + perm_results
    if env_vars:
        # 只统计必需配置项的问题
        required_keys = ['BOT_TOKEN', 'BOT_USERNAME', 'CHANNEL_ID']
        config_results = check_env_config(env_vars)
        required_results = [(k, s, d) for k, s, d in config_results if k in required_keys]
        all_results.extend(required_results)
    
    failed_checks = [r for r in all_results if not r[1]]
    
    if failed_checks:
        print(f"{Colors.RED}发现 {len(failed_checks)} 个问题需要修复:{Colors.ENDC}")
        for name, _, details in failed_checks:
            print(f"  • {name}: {details}")
        
        # 生成修复脚本
        fix_script = generate_fix_script(env_vars)
        fix_script_path = Path('fix_config.sh')
        
        try:
            with open(fix_script_path, 'w', encoding='utf-8') as f:
                f.write(fix_script)
            
            # 添加执行权限
            import stat
            fix_script_path.chmod(fix_script_path.stat().st_mode | stat.S_IXUSR)
            
            print(f"\n{Colors.GREEN}已生成修复脚本: {fix_script_path}{Colors.ENDC}")
            print(f"运行命令: {Colors.YELLOW}./fix_config.sh{Colors.ENDC}")
        
        except Exception as e:
            print(f"{Colors.RED}生成修复脚本失败: {e}{Colors.ENDC}")
    
    else:
        print(f"{Colors.GREEN}✅ 所有检查都通过了！{Colors.ENDC}")
        print(f"你可以运行以下命令启动机器人:")
        print(f"  开发模式: {Colors.YELLOW}python -m orderbot{Colors.ENDC}")
        print(f"  Docker 开发: {Colors.YELLOW}./deploy.sh start{Colors.ENDC}")
        print(f"  Docker 生产: {Colors.YELLOW}./deploy.sh start --prod{Colors.ENDC}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}检查被用户中断{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}检查过程中发生错误: {e}{Colors.ENDC}")
        sys.exit(1)