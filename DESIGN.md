# DESIGN — Telegram 工单管理 Bot（MVP）

## 1. 架构概览
- 运行模式：aiogram + SQLite（aiosqlite 驱动）+ 长轮询。保留切换 Webhook + FastAPI 的接口（Router、Service、Repo 解耦）。
- 分层：
  - tg：Bot/Dispatcher/Router、Handlers（发布/审核/公开交互）、Keyboards、Middlewares
  - services：业务编排（订单创建、申请接单、审批、完成、列表）与频道发布器
  - core：数据库连接、ORM 模型、仓储（Repo）
  - utils：日志与公共工具

```
[Telegram] <—updates—> [aiogram Bot]
         handlers —(service调用)→ services —(repo)→ core(db)
         handlers —(publisher)→ channel message (publish/edit)
```

## 2. 模块与职责
- tg.bot：初始化 Bot/Dispatcher/Router，加载中间件与 handlers。
- tg.handlers_publish：发布流程（FSM/Wizard）：/start, 发布向导（标题/内容/金额/媒体）。
- tg.handlers_review：待审核分页、「✅同意」「❌拒绝」、以及完成操作入口。
- tg.handlers_public：频道按钮回调：「我要接单」「📋 订单列表」及私聊列表分页。
- tg.keyboards：生成 inline keyboards（申请接单、订单列表、审核操作）。
- tg.middlewares：
  - 白名单鉴权：管理员/白名单校验；仅管理员能审核与完成。
  - 速率限制：5s/次，限制回调（apply/approve/reject/done/cancel）与 /update 命令。
  - 异常捕获：统一处理并记录 trace_id。
- core.db：创建异步引擎与 session 工厂，提供 get_session() 上下文。
- core.models：SQLAlchemy ORM（orders, order_media, order_applications, order_status_history）。
- core.repo：通用 CRUD 与订单查询，写入历史，预留 for_update（Postgres）。
- services.order_service：create/apply/approve/reject/update/done/list；校验状态机与权限；写 history；调用 publisher。
- services.channel_publisher：发布/编辑频道消息（渲染文本与按钮），失败重试与日志；支持媒体组。
- utils.logging：结构化日志封装（添加 order_id、actor_tg_user_id、status_from、status_to 等字段）。

## 3. ER 模型
- orders(
  id pk, title, content, amount nullable,
  status enum[NEW,IN_PROGRESS,DONE,CANCELED],
  created_by, created_by_username,
  claimed_by nullable, claimed_by_username nullable,
  channel_message_id nullable,
  created_at, updated_at,
  version int default 0
)
- order_media(
  id pk, order_id fk→orders.id,
  kind enum[photo,video,document],
  file_id, position int
)
- order_applications(
  id pk, order_id fk→orders.id,
  applicant_tg_id, applicant_username,
  status enum[PENDING,APPROVED,REJECTED],
  note nullable, created_at, decided_at nullable,
  UNIQUE(order_id, applicant_tg_id)
)
- order_status_history(
  id pk, order_id fk→orders.id,
  from_status nullable, to_status,
  actor_user_id, note nullable, created_at
)

关系：orders 1—* order_media；orders 1—* order_applications；orders 1—* order_status_history。

## 4. 状态机与规则
- 主路径：NEW → IN_PROGRESS → DONE
- 取消：NEW/IN_PROGRESS → CANCELED
- 申请接单（apply）：仅创建 application 记录，不改变订单状态。
- 审核同意（approve）：将 NEW → IN_PROGRESS，并设置 claimed_by 与用户名；写 history。
- 审核拒绝（reject）：application → REJECTED，并通知申请人；订单状态不变。
- 完成（done）：仅管理员或 claimed_by 可将 IN_PROGRESS → DONE；写 history。
- 非法跳转：抛出业务异常并拒绝；写失败日志。

## 5. 权限矩阵（MVP）
- 发布订单：与 Bot 私聊的任意用户可发起。
- 申请接单：受 ALLOW_ANYONE_APPLY 控制；为 false 时仅管理员/白名单可申请。
- 审核同意/拒绝、完成：仅 ALLOWED_ADMIN_IDS 列表中的管理员可执行；完成亦允许 claimed_by 执行。

## 6. 幂等与健壮性
- 发布频道消息：若已存在 channel_message_id 则不重复发布（转为编辑）。
- 编辑频道消息：比对渲染内容避免重复编辑；失败保留上下文信息。
- 回调解析：严格解析 act 与 oid；缺失或非法直接拒绝并 toast 提示。

## 7. 失败重试与编辑策略
- publish/edit 失败：重试 3 次，指数退避（0.5s/1s/2s）。
- 持续失败：ERROR 级日志并附上下文（order_id、message_id、actor）。

## 8. 安全策略
- 白名单鉴权：ALLOWED_ADMIN_IDS 解析为集合；仅管理员能审核/完成。
- 速率限制：基于内存 kv；对 apply/approve/reject/done/cancel 与 /update 实施 5s 窗口。
- 机密：通过 .env 注入；不在代码中硬编码。

## 9. 可观测性
- 结构化日志：成功/失败事件；核心字段；trace_id（uuid4）。
- 指标：后续可引入计数器；MVP 以日志代替。

## 10. 渲染规范与交互
- 频道贴文文本：
  - 标题
  - 内容
  - 金额（可选，存在时展示）
  - 状态与处理人（IN_PROGRESS/DONE/CANCELED 时展示处理人）
  - 引导文案（含与 Bot 私聊提示）
- 按钮：
  - 「我要接单」callback_data="act=apply;oid=<id>"
  - 「📋 订单列表」callback_data="act=list"
- 深链：
  - 联系运营：tg://user?id=${OPERATOR_USER_ID}（优先），否则 https://t.me/${OPERATOR_USERNAME}
  - 与 Bot： https://t.me/${BOT_USERNAME}?start=apply_<order_id>
- 媒体策略：
  - 发布首媒体+文本或媒体组 + 文本卡片；保存 file_id 以复用。

## 11. 配置与切换
- config.Settings：从 .env 读取 BOT_TOKEN, BOT_USERNAME, CHANNEL_ID, OPERATOR_USER_ID/USERNAME, ALLOWED_ADMIN_IDS, ALLOW_ANYONE_APPLY, DATABASE_URL, LOG_LEVEL。
- 运行模式：默认长轮询；保留 webhook/fastapi 切换位（TODO）。

## 12. 目录结构（落地）
- src/tg/handlers_publish.py
- src/tg/handlers_review.py
- src/tg/handlers_public.py
（其余按项目根要求）

## 13. 关键接口（摘要）
- repo：
  - get_order_by_id(order_id)
  - list_new_orders(offset, limit)
  - create_application(order_id, user_id, username) 幂等（唯一键）
  - update_order_fields(order_id, **fields)
  - create_history(order_id, from_status, to_status, actor_user_id, note=None)
- service：
  - create_order(user, payload, media_files) -> Order
  - apply_order(order_id, actor) -> Application + 深链文案
  - approve_application(order_id, applicant) -> Order
  - reject_application(order_id, applicant, note=None)
  - mark_done(order_id, actor) -> Order
  - list_new_orders(page, page_size)
- publisher：
  - publish_order_to_channel(order, media) -> message_id
  - edit_order_message(order)

## 14. 风险与对策（MVP）
- 频道编辑失败：采用重试+保底日志；可后续引入任务队列重试。
- SQLite 并发：低并发场景可接受；预留 for_update 接口以便未来切 Postgres。
- 回调滥用：白名单+速率限制+健壮解析。

---
本设计文档与 ALIGNMENT 保持一致，如有出入以本文件为准并回写修订。