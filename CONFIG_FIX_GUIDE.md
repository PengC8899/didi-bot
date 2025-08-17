# 配置修复指南

根据配置检查结果，发现以下问题需要修复：

## 🔧 需要修复的问题

### 1. BOT_TOKEN 未配置
**问题**: 机器人令牌使用默认值或未配置  
**影响**: 导致 `net::ERR_ABORTED` 和 `net::ERR_FAILED` 错误，机器人无法连接到 Telegram API

**解决步骤**:
1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/newbot` 创建新机器人（如果还没有）
3. 按提示设置机器人名称和用户名
4. 复制获得的 BOT_TOKEN（格式类似：`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`）
5. 编辑 `.env` 文件，替换以下行：
   ```bash
   BOT_TOKEN="你的真实机器人令牌"
   ```

### 2. CHANNEL_ID 未配置
**问题**: 频道ID使用默认值  
**影响**: 机器人无法向正确的频道发送消息

**解决步骤**:
1. 将机器人添加到你的频道作为管理员
2. 在频道中发送一条消息
3. 访问：`https://api.telegram.org/bot你的BOT_TOKEN/getUpdates`
4. 在返回的JSON中找到 `"chat":{"id":-1001234567890}` 这样的负数ID
5. 编辑 `.env` 文件，替换以下行：
   ```bash
   CHANNEL_ID="-1001234567890"  # 替换为你的真实频道ID
   ```

## 🚀 快速修复命令

1. **运行自动修复脚本**（修复文件权限）：
   ```bash
   ./fix_config.sh
   ```

2. **手动编辑配置文件**：
   ```bash
   nano .env
   # 或者使用其他编辑器
   code .env
   ```

3. **验证修复结果**：
   ```bash
   python check_config.py
   ```

## 📋 完整的 .env 配置示例

```bash
# Telegram Bot 配置
BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"  # 替换为真实令牌
BOT_USERNAME="your_bot_username"                    # 替换为真实用户名
CHANNEL_ID="-1001234567890"                        # 替换为真实频道ID

# 运营人员配置
OPERATOR_USER_ID="123456789"                       # 运营人员的用户ID
OPERATOR_USERNAME="operator_username"              # 运营人员的用户名

# 权限配置
ALLOWED_ADMIN_IDS="123456789,987654321"           # 管理员ID列表，用逗号分隔
ALLOW_ANYONE_APPLY="false"                         # false时仅管理员可申请

# 兼容历史字段
ALLOWED_USER_IDS=""                               # 历史白名单变量名，继续兼容

# 数据库配置
DATABASE_URL="sqlite:///orderbot.db"

# 日志配置
LOG_LEVEL="INFO"
```

## 🔍 错误排查

### `net::ERR_ABORTED` 和 `net::ERR_FAILED` 错误
这些错误通常由以下原因引起：

1. **BOT_TOKEN 无效**
   - 检查令牌是否正确复制
   - 确认机器人未被删除或禁用
   - 重新从 @BotFather 获取令牌

2. **网络连接问题**
   - 检查网络连接
   - 确认防火墙未阻止 Telegram API
   - 尝试使用代理（如果在受限网络环境）

3. **权限问题**
   - 确认机器人有足够权限
   - 检查频道设置

### `deploy.sh monitor` 命令问题
如果遇到 `E486: Pattern not found: deploy.sh monitor` 错误：

1. **确认文件存在**：
   ```bash
   ls -la deploy.sh
   ```

2. **检查文件权限**：
   ```bash
   chmod +x deploy.sh
   ```

3. **验证命令**：
   ```bash
   ./deploy.sh --help
   ```

4. **查看监控服务**：
   ```bash
   ./deploy.sh monitor
   ```

## ✅ 验证修复

修复配置后，按以下步骤验证：

1. **运行配置检查**：
   ```bash
   python check_config.py
   ```

2. **测试机器人连接**：
   ```bash
   python -c "import asyncio; from aiogram import Bot; asyncio.run(Bot('你的BOT_TOKEN').get_me())"
   ```

3. **启动机器人**：
   ```bash
   # 开发模式
   python -m orderbot
   
   # 或 Docker 模式
   ./deploy.sh start
   ```

4. **检查日志**：
   ```bash
   tail -f logs/orderbot.log
   ```

## 🆘 获取帮助

如果问题仍然存在：

1. 查看详细日志：`tail -f logs/orderbot.log`
2. 检查 Docker 日志：`docker logs orderbot`
3. 运行故障排除：`python check_config.py`
4. 查看故障排除指南：`cat TROUBLESHOOTING.md`

---

**注意**: 请妥善保管你的 BOT_TOKEN，不要将其提交到版本控制系统或公开分享。