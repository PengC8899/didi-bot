# Telegram 工单管理 Bot (MVP)

一个基于 aiogram + SQLite + SQLAlchemy (async) 的 Telegram 工单管理机器人，支持工单创建、认领、状态跟踪和频道发布。

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入机器人配置

# 2. 启动服务
./deploy.sh start

# 3. 查看日志
./deploy.sh logs
```

详细的 Docker 部署说明请参考 [DOCKER_DEPLOY.md](DOCKER_DEPLOY.md)

### 方式二：本地开发部署

```bash
# 1. 安装依赖
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .

# 2. 配置环境
cp .env.example .env
# 编辑 .env 文件，填入以下必要变量：
# - BOT_TOKEN: 从 @BotFather 获取的机器人令牌
# - CHANNEL_ID: 工单发布频道的 ID（如：-1001234567890）
# - OPERATOR_USER_ID 或 OPERATOR_USERNAME: 运营人员联系方式（可选）
# - ALLOWED_USER_IDS: 白名单用户 ID，逗号分隔（留空表示不限制）

# 3. 启动机器人
python -m orderbot.src.app
```

## 功能特性

### 基础命令
- `/start` - 查看帮助信息
- `/neworder 标题 | 内容 | [金额]` - 创建工单
- `/myorders` - 查看与您相关的工单

### 工单管理
- 支持状态机：NEW → CLAIMED → IN_PROGRESS → DONE
- 支持取消：NEW/CLAIMED/IN_PROGRESS → CANCELED
- 自动发布到频道并同步状态更新
- 完整的操作历史记录

### 安全特性
- 白名单用户鉴权（可配置）
- 速率限制保护（5秒内限制1次操作）
- 异常捕获与错误日志
- 敏感信息环境变量注入

## 开发与测试

### 运行测试

```bash
# 运行全部测试
pytest -q --maxfail=1 --disable-warnings

# 运行测试并生成覆盖率报告
coverage run -m pytest && coverage report -m
```

### 测试覆盖范围

项目包含 13 个测试用例，覆盖以下关键场景：
1. 创建订单 → 状态 NEW，history 记录 
2. NEW→CLAIMED 成功转换
3. 认领后频道消息编辑调用
4. 状态机非法跳转保护
5. /update 命令权限与状态更新
6. /myorders 用户相关订单查询
7. 回调解析健壮性（异常输入处理）
8. 仓储层幂等与异常路径

当前测试覆盖率：**78%**

## 架构设计

```
orderbot/
├── src/
│   ├── config.py           # 环境变量配置
│   ├── app.py             # 应用入口（长轮询）
│   ├── core/              # 核心数据层
│   │   ├── db.py          # 数据库连接
│   │   ├── models.py      # SQLAlchemy 模型
│   │   └── repo.py        # 仓储层
│   ├── services/          # 业务服务层
│   │   ├── order_service.py      # 订单业务逻辑
│   │   └── channel_publisher.py  # 频道发布服务
│   ├── tg/               # Telegram Bot 层
│   │   ├── bot.py        # 路由与处理器
│   │   ├── keyboards.py  # 按钮键盘
│   │   └── middlewares.py # 中间件（鉴权/限流/异常）
│   ├── utils/            # 工具模块
│   │   └── logging.py    # 结构化日志
│   └── tests/            # 单元测试
└── pyproject.toml        # 项目配置
```

## 环境变量

| 变量名 | 必填 | 说明 | 示例 |
|--------|------|------|------|
| `BOT_TOKEN` | ✅ | Telegram Bot Token | `1234567890:AAEhBOweik6ad9r2N-KjcCGPqaky_E1...` |
| `CHANNEL_ID` | ✅ | 工单发布频道 ID | `-1001234567890` |
| `OPERATOR_USER_ID` | ❌ | 运营人员用户 ID | `123456789` |
| `OPERATOR_USERNAME` | ❌ | 运营人员用户名 | `@operator` |
| `ALLOWED_USER_IDS` | ❌ | 白名单用户（逗号分隔） | `12345,67890` |
| `DATABASE_URL` | ❌ | 数据库连接串 | `sqlite+aiosqlite:///./orderbot.db` |
| `LOG_LEVEL` | ❌ | 日志级别 | `INFO` |

## 注意事项

1. **数据库**：默认使用 SQLite，适用于中小规模部署。生产环境建议切换到 PostgreSQL。

2. **私聊权限**：用户需要先与机器人私聊过才能接收私信回复。

3. **频道配置**：确保机器人已被添加到目标频道并具有发送消息权限。

4. **白名单**：如果配置了 `ALLOWED_USER_IDS`，只有白名单内的用户可以使用机器人。

## 故障排除

### 常见问题

1. **机器人无响应**
   - 检查 `BOT_TOKEN` 是否正确
   - 确认网络连接正常

2. **频道发布失败**
   - 检查 `CHANNEL_ID` 格式（需包含负号）
   - 确认机器人已加入频道且有发言权限

3. **数据库错误**
   - 检查 `DATABASE_URL` 配置
   - 确认文件系统权限（SQLite）

### 日志查看

程序使用结构化日志，关键事件包括：
- `order.created`：订单创建
- `channel.publish.success/failed`：频道发布结果
- `channel.edit.success/failed`：频道编辑结果
- `auth.whitelist.denied`：白名单拒绝
- `ratelimit.blocked`：速率限制

## License

MIT License

# Order Bot

## 创建工单

现在支持两种方式：

- 引导式（推荐）
  1. 发送 `/neworder`
  2. 按提示依次回复：标题 → 内容 → 金额（可留空或输入 0 表示无金额）
  3. 机器人展示汇总后，回复“确认/是/yes/y”创建，或“取消/cancel”放弃
  4. 任意阶段支持 `/cancel` 取消当前操作

- 快捷式（兼容旧格式）
  - 发送：`/neworder 标题 | 内容 | [金额]`
  - 金额为可选；若不是数字或缺省，将按“无金额”处理

## 常用命令
- `/start` 查看使用指引（已更新说明引导式与快捷式）
- `/neworder` 创建新工单（支持引导式和旧格式）
- `/cancel` 取消当前进行中的创建流程
- `/myorders` 查看与您相关的工单