# 故障排除指南

## 常见问题及解决方案

### 1. 网络连接错误

#### 问题现象
```
net::ERR_ABORTED tg://resolve?domain=PccSSR_bot
net::ERR_FAILED https://telegram.org/
```

#### 原因分析
这些错误通常由以下原因引起：
1. **BOT_TOKEN 未正确配置**：当前配置为默认值 `YOUR_TELEGRAM_BOT_TOKEN`
2. **网络连接问题**：无法访问 Telegram API
3. **机器人配置错误**：BOT_USERNAME 或其他配置不正确

#### 解决步骤

1. **检查并更新 BOT_TOKEN**
   ```bash
   # 编辑 .env 文件
   nano .env
   
   # 将 BOT_TOKEN 替换为真实的机器人令牌
   BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
   BOT_USERNAME="your_actual_bot_username"
   CHANNEL_ID="-1001234567890"  # 替换为实际频道ID
   ```

2. **验证机器人配置**
   ```bash
   # 测试机器人连接
   python -c "import os; from aiogram import Bot; bot = Bot(token=os.getenv('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')); print('Token valid' if bot.token != 'YOUR_TELEGRAM_BOT_TOKEN' else 'Please set real BOT_TOKEN')"
   ```

3. **检查网络连接**
   ```bash
   # 测试 Telegram API 连接
   curl -s "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"
   ```

### 2. deploy.sh monitor 命令问题

#### 问题现象
```
E486: Pattern not found: deploy.sh monitor
```

#### 原因分析
1. **当前目录错误**：不在项目根目录执行命令
2. **文件权限问题**：deploy.sh 没有执行权限
3. **编辑器搜索问题**：在 vim/vi 中搜索时的错误

#### 解决步骤

1. **确认当前目录**
   ```bash
   pwd
   ls -la deploy.sh
   ```

2. **添加执行权限**
   ```bash
   chmod +x deploy.sh
   ```

3. **正确执行命令**
   ```bash
   # 在项目根目录执行
   ./deploy.sh monitor
   
   # 或者查看帮助
   ./deploy.sh help
   ```

### 3. 权限配置问题

#### 问题现象
- 用户无法使用管理员功能
- ALLOWED_USER_IDS 配置混乱

#### 解决步骤

1. **配置管理员权限**
   ```bash
   # 编辑 .env 文件
   nano .env
   
   # 设置管理员ID（替换为实际用户ID）
   ALLOWED_ADMIN_IDS="123456789,987654321"
   ALLOWED_USER_IDS="123456789,987654321"  # 兼容历史配置
   ```

2. **获取用户ID**
   - 发送消息给 @userinfobot 获取自己的用户ID
   - 或在机器人日志中查看用户ID

### 4. 数据库连接问题

#### 检查数据库状态
```bash
# 检查数据库文件
ls -la orderbot.db

# 检查数据库连接
python -c "import asyncio; from orderbot.src.core.database import init_engine, get_session; asyncio.run(init_engine('sqlite+aiosqlite:///./orderbot.db'))"
```

### 5. Docker 相关问题

#### 容器无法启动
```bash
# 查看容器状态
docker ps -a

# 查看容器日志
docker logs orderbot-dev

# 重新构建镜像
docker-compose build --no-cache
```

#### 监控服务问题
```bash
# 检查监控服务状态
docker-compose -f docker-compose.monitoring.yaml ps

# 重启监控服务
./deploy.sh monitor
```

## 配置检查清单

### 必需配置项
- [ ] BOT_TOKEN：真实的机器人令牌
- [ ] BOT_USERNAME：机器人用户名（不含@）
- [ ] CHANNEL_ID：频道ID（负数）

### 可选配置项
- [ ] OPERATOR_USER_ID：运营人员用户ID
- [ ] OPERATOR_USERNAME：运营人员用户名
- [ ] ALLOWED_ADMIN_IDS：管理员ID列表
- [ ] ALLOW_ANYONE_APPLY：是否允许任何人申请

## 日志分析

### 查看实时日志
```bash
# 开发环境
python -m orderbot

# Docker 环境
docker logs -f orderbot-dev

# 生产环境
docker logs -f orderbot-prod
```

### 常见日志错误

1. **Token 错误**
   ```
   aiogram.exceptions.TelegramUnauthorizedError: Unauthorized
   ```
   解决：检查 BOT_TOKEN 配置

2. **频道权限错误**
   ```
   aiogram.exceptions.TelegramForbiddenError: Forbidden
   ```
   解决：确保机器人已添加到频道并有发送消息权限

3. **数据库连接错误**
   ```
   sqlalchemy.exc.OperationalError
   ```
   解决：检查数据库文件权限和路径

## 获取帮助

如果以上解决方案都无法解决问题，请：

1. 收集错误日志
2. 检查配置文件
3. 确认网络连接
4. 查看 GitHub Issues 或创建新的 Issue

## 快速诊断脚本

创建并运行诊断脚本：

```bash
# 创建诊断脚本
cat > diagnose.py << 'EOF'
import os
import asyncio
from pathlib import Path

async def diagnose():
    print("=== 配置诊断 ===")
    
    # 检查环境变量
    bot_token = os.getenv('BOT_TOKEN', 'NOT_SET')
    print(f"BOT_TOKEN: {'✅ 已设置' if bot_token != 'YOUR_TELEGRAM_BOT_TOKEN' and bot_token != 'NOT_SET' else '❌ 未设置或为默认值'}")
    
    bot_username = os.getenv('BOT_USERNAME', 'NOT_SET')
    print(f"BOT_USERNAME: {'✅ 已设置' if bot_username != 'your_bot_username' and bot_username != 'NOT_SET' else '❌ 未设置或为默认值'}")
    
    channel_id = os.getenv('CHANNEL_ID', 'NOT_SET')
    print(f"CHANNEL_ID: {'✅ 已设置' if channel_id != '-1001234567890' and channel_id != 'NOT_SET' else '❌ 未设置或为默认值'}")
    
    # 检查文件
    print("\n=== 文件检查 ===")
    files_to_check = ['.env', 'deploy.sh', 'orderbot.db']
    for file in files_to_check:
        path = Path(file)
        if path.exists():
            print(f"{file}: ✅ 存在")
        else:
            print(f"{file}: ❌ 不存在")
    
    # 检查权限
    deploy_sh = Path('deploy.sh')
    if deploy_sh.exists():
        import stat
        mode = deploy_sh.stat().st_mode
        executable = bool(mode & stat.S_IXUSR)
        print(f"deploy.sh 可执行权限: {'✅ 有' if executable else '❌ 无'}")

if __name__ == '__main__':
    asyncio.run(diagnose())
EOF

# 运行诊断
python diagnose.py
```

这个诊断脚本会检查常见的配置问题并给出建议。