# TASK — Telegram 工单管理 Bot（MVP）

优先级分层：P0 为必须完成以形成可运行与可测的 MVP；P1 为增强与未来留口。

## P0 任务
1. 项目脚手架与配置
   - DoD：创建目录结构；pyproject.toml；.env.example；README 基本运行命令；pytest 配置。
2. 配置与加载
   - DoD：实现 src/config.py（pydantic Settings），解析 BOT_USERNAME、ALLOWED_ADMIN_IDS、ALLOW_ANYONE_APPLY、CHANNEL_ID、OPERATOR_*、DATABASE_URL、LOG_LEVEL；单测覆盖。
3. 日志
   - DoD：utils/logging.py 提供结构化日志器，含关键字段；异常 ERROR 级；单测基本验证。
4. 数据层
   - DoD：core/db.py 异步 engine+session；core/models.py 四表与枚举（orders/order_media/order_applications/order_status_history）；core/repo.py 基本 CRUD + 幂等工具与分页；单测覆盖。
5. 业务层
   - DoD：services/order_service.py：create/apply/approve/reject/done/list；校验状态机与权限；写入 history；调用 publisher；单测覆盖状态机与异常路径。
6. 频道发布器
   - DoD：services/channel_publisher.py：publish/edit，含重试（0.5/1/2s）、幂等、渲染文本与按钮；可被 mock；单测覆盖调用点与失败重试。
7. 机器人初始化
   - DoD：tg/bot.py 初始化 Bot/Dispatcher/Router；加载中间件与 handlers。
8. 中间件
   - DoD：tg/middlewares.py：白名单（管理员）鉴权、5s 速率限制、异常捕获；关键路径单测。
9. 键盘与渲染
   - DoD：tg/keyboards.py：
     - 频道按钮：「我要接单」(act=apply;oid=<id>)、「📋 订单列表」(act=list)
     - 审核按钮：「✅同意」「❌拒绝」
     - 单测覆盖按钮数据与深链生成。
10. 处理器
   - DoD：
     - tg/handlers_publish.py：/start, 发布向导（标题/内容/金额/媒体）
     - tg/handlers_review.py：待审核分页、同意/拒绝、完成
     - tg/handlers_public.py：频道按钮回调（apply/list）、私聊订单列表分页
     - 单测覆盖解析、权限与异常分支。
11. 入口
   - DoD：src/app.py：长轮询启动，异常退出日志。
12. 单元测试（≥10）
   - DoD：完成并通过以下 10 项测试：
     1) 发布订单：DB/频道均成功、保存 message_id、媒体 file_id 正确
     2) 申请接单：application 记录创建、回发两段式深链
     3) 重复申请：被幂等拒绝（唯一键生效）
     4) 审核同意：NEW→IN_PROGRESS，claimed_by 填充，频道编辑被调用
     5) 审核拒绝：application 标记 REJECTED，申请人收到通知
     6) 完成订单：IN_PROGRESS→DONE，history 记录
     7) 非法状态跳转报错
     8) 非管理员尝试审核被拒绝
     9) 「订单列表」分页正确，边界页正常
     10) 频道编辑失败自动重试与日志记录

## P1 任务
1. Webhook + FastAPI 管理口
   - DoD：新增 ASGI 应用骨架，健康检查；可切换运行模式。
2. Postgres 切换与 Alembic 迁移
   - DoD：新增 Postgres 连接配置；alembic 模板；for_update 生效。
3. 可观测性增强
   - DoD：简单指标收集器；错误率与编辑失败次数导出。
4. 安全与重试增强
   - DoD：消息幂等键（去重表）；重试策略外部化配置；RBAC 角色表。
5. Docker
   - DoD：docker-compose.yaml 示例与启动参数；restart: always。

## 交付顺序
P0 全部 → 测试与覆盖率 → 运行示例；随后依次处理 P1。

## 风险与依赖
- 依赖 Telegram API 可用性；失败需重试与日志。
- SQLite 并发有限；低并发场景可接受。
- 用户私聊权限受限（用户未开启与 Bot 对话时无法私聊）。

---
审批通过后，进入 Automate 阶段按本清单实施。