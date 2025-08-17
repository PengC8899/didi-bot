# Docker 部署指南

本文档介绍如何使用 Docker 部署 Telegram 订单管理机器人。

## 前置要求

- Docker Engine 20.10+
- Docker Compose 2.0+
- 已配置的 Telegram Bot Token

## 环境配置

### 配置文件说明

项目提供两种部署配置：

- **开发环境** (`docker-compose.yaml`): 适用于开发和测试
- **生产环境** (`docker-compose.prod.yaml`): 适用于生产部署，包含更严格的资源限制和安全配置

### 主要差异

| 配置项 | 开发环境 | 生产环境 |
|--------|----------|----------|
| 资源限制 | 较宽松 | CPU: 1核, 内存: 1GB |
| 健康检查 | 基础配置 | 更严格的检查间隔 |
| 日志管理 | 10MB × 3文件 | 50MB × 5文件 |
| 网络隔离 | 默认网络 | 独立网络 |
| 启动等待时间 | 40秒 | 60秒 |

## 快速开始

### 1. 准备环境变量

复制环境变量模板并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入必要的配置：

```bash
# 必填项
BOT_TOKEN="你的机器人Token"
BOT_USERNAME="你的机器人用户名"  # 不含@
CHANNEL_ID="-1001234567890"     # 频道ID
OPERATOR_USER_ID="123456789"    # 运营人员用户ID
ALLOWED_ADMIN_IDS="123456789"   # 管理员ID列表，逗号分隔

# 可选项
ALLOW_ANYONE_APPLY="true"        # 是否允许任何人申请接单
LOG_LEVEL="INFO"                 # 日志级别
```

### 2. 创建必要目录

```bash
mkdir -p data images logs
```

### 3. 构建并启动服务

#### 开发环境（默认）
```bash
# 构建并启动
./deploy.sh start
# 或明确指定开发环境
./deploy.sh start --dev

# 查看日志
./deploy.sh logs --dev

# 查看状态
./deploy.sh status --dev
```

#### 生产环境
```bash
# 构建并启动
./deploy.sh start --prod

# 查看日志
./deploy.sh logs --prod

# 查看状态
./deploy.sh status --prod
```

#### 传统 Docker Compose 方式
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d
```

### 4. 查看日志

```bash
# 查看实时日志
docker-compose logs -f orderbot

# 查看最近100行日志
docker-compose logs --tail=100 orderbot
```

## 管理命令

### 部署脚本使用
```bash
# 查看帮助
./deploy.sh help

# 启动服务
./deploy.sh start [--prod|--dev]

# 停止服务
./deploy.sh stop [--prod|--dev]

# 重启服务
./deploy.sh restart [--prod|--dev]

# 查看日志
./deploy.sh logs [--prod|--dev]

# 查看状态
./deploy.sh status [--prod|--dev]

# 重新构建
./deploy.sh build

# 管理监控服务
./deploy.sh monitor

# 清理所有资源（危险操作）
./deploy.sh clean
```

### 监控服务

项目提供完整的监控解决方案，包含：

- **Prometheus**: 指标收集和存储 (http://localhost:9090)
- **Grafana**: 数据可视化面板 (http://localhost:3000)
- **cAdvisor**: 容器资源监控 (http://localhost:8080)
- **Node Exporter**: 系统指标监控 (http://localhost:9100)

```bash
# 启动监控服务
./deploy.sh monitor

# 或直接使用 Docker Compose
docker-compose -f docker-compose.monitoring.yaml up -d

# 停止监控服务
docker-compose -f docker-compose.monitoring.yaml down
```

**默认登录信息**:
- Grafana: admin / admin123

### 停止服务

```bash
docker-compose down
```

### 重启服务

```bash
docker-compose restart orderbot
```

### 更新服务

```bash
# 停止服务
docker-compose down

# 重新构建镜像
docker-compose build --no-cache

# 启动服务
docker-compose up -d
```

### 进入容器调试

```bash
docker-compose exec orderbot bash
```

## 数据持久化

容器使用以下卷进行数据持久化：

- `./data:/app/data` - 数据库文件存储
- `./images:/app/images` - 图片文件存储
- `./logs:/app/logs` - 日志文件存储

## 健康检查

容器配置了健康检查，可以通过以下命令查看状态：

```bash
docker-compose ps
```

健康状态说明：
- `healthy` - 服务正常运行
- `unhealthy` - 服务异常
- `starting` - 服务启动中

## 资源限制

默认配置的资源限制：
- CPU: 最大 0.5 核心，预留 0.25 核心
- 内存: 最大 512MB，预留 256MB

可以在 `docker-compose.yaml` 中调整这些限制。

## 日志管理

容器配置了日志轮转：
- 单个日志文件最大 10MB
- 最多保留 3 个日志文件
- 使用 JSON 格式记录日志

## 故障排除

### 1. 容器无法启动

检查环境变量配置：
```bash
docker-compose config
```

查看详细错误信息：
```bash
docker-compose logs orderbot
```

### 2. 机器人无响应

检查 Telegram Bot Token 是否正确：
```bash
docker-compose exec orderbot python -c "from orderbot.src.config import Settings; print('Token:', Settings().BOT_TOKEN[:10] + '...')"
```

### 3. 数据库问题

检查数据库文件权限：
```bash
ls -la data/
```

重新初始化数据库：
```bash
docker-compose exec orderbot python -c "from orderbot.src.core.db import init_engine; import asyncio; asyncio.run(init_engine('sqlite+aiosqlite:///./data/orderbot.db'))"
```

### 4. 清理和重置

完全清理并重新开始：
```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi ddgl_bot-orderbot

# 清理数据（注意：这会删除所有数据）
rm -rf data/* logs/*

# 重新构建和启动
docker-compose build --no-cache
docker-compose up -d
```

## 生产环境建议

1. **使用外部数据库**：考虑使用 PostgreSQL 替代 SQLite
2. **配置反向代理**：如果需要 Webhook 模式，配置 Nginx 或 Traefik
3. **监控和告警**：集成 Prometheus + Grafana 进行监控
4. **备份策略**：定期备份 `data` 目录
5. **安全加固**：使用非 root 用户运行容器（已配置）

## 环境变量完整列表

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `BOT_TOKEN` | ✅ | - | Telegram Bot Token |
| `BOT_USERNAME` | ✅ | - | 机器人用户名（不含@） |
| `CHANNEL_ID` | ✅ | - | 订单发布频道ID |
| `OPERATOR_USER_ID` | ❌ | - | 运营人员用户ID |
| `OPERATOR_USERNAME` | ❌ | - | 运营人员用户名 |
| `ALLOWED_ADMIN_IDS` | ❌ | - | 管理员ID列表（逗号分隔） |
| `ALLOW_ANYONE_APPLY` | ❌ | `true` | 是否允许任何人申请接单 |
| `DATABASE_URL` | ❌ | `sqlite+aiosqlite:///./data/orderbot.db` | 数据库连接URL |
| `LOG_LEVEL` | ❌ | `INFO` | 日志级别 |

## 支持

如果遇到问题，请检查：
1. Docker 和 Docker Compose 版本
2. 环境变量配置
3. 网络连接
4. Telegram API 可用性

更多技术细节请参考项目的其他文档文件。