# ALIGNMENT — Telegram 订单管理 Bot（MVP）

## 1. 项目背景与目标
- 目标：构建一个基于 Telegram 的工单管理机器人，支持创建/查看/更新工单、记录状态流转历史，并在指定频道发布和更新工单贴文，便于运营团队分发与跟进。
- 业务价值：降低沟通成本、提高接单与跟单效率、形成可追踪的结构化数据沉淀。
- 成果形态：一套可运行的 aiogram + SQLite 长轮询 Bot（可平滑切换 Webhook + FastAPI），附带单元测试与README。

## 2. 角色与权限（初版）
- Bot：执行业务逻辑、发送/编辑频道消息、接收命令与回调。
- 管理员（admin/channel admin）：拥有审批与完成权限（由环境变量 ALLOWED_ADMIN_IDS 配置）。
- 运营（operator）：可作为联系窗口，供申请者私聊咨询（深链跳转）。
- 普通用户：可浏览频道贴文并发起“我要接单”（受 ALLOW_ANYONE_APPLY 开关控制）。

## 3. 范围（Scope）
In Scope（MVP）
- 私聊主菜单：
  - 📝 发布订单：引导填写 标题/内容/金额(可选)，支持收集 0~N 媒体；落库后发布到频道并记录 channel_message_id。
  - 🕒 待审核：管理员分页查看每个订单的申请人，提供 ✅同意 / ❌拒绝。
  - ✅ 已完成：将进行中的订单标记为 DONE 并同步频道。
  - 📋 订单列表：私聊分页查看所有 status=NEW 的订单。
- 频道贴文按钮：
  - 「我要接单」(callback_data="act=apply;oid=<id>")：仅写入 order_applications，状态不变；回传两段式深链（联系运营 + 与 Bot 的 start 深链）。
  - 「📋 订单列表」(callback_data="act=list")：引导用户私聊查看分页列表。
- 审核流：
  - 同意：将订单 NEW → IN_PROGRESS，并设置 claimed_by / claimed_by_username；编辑频道贴文与按钮。
  - 拒绝：标记 application 为 REJECTED，并通知申请人。
- 数据一致性：每次状态变化更新 DB 并编辑频道贴文（幂等）；失败重试 3 次并记录日志与告警。

Out of Scope（MVP 之外）
- Webhook 与管理后台（保留接口，后续版本实现）。
- Postgres 与 Alembic 迁移（预留切换口）。
- 完整 RBAC、审计导出、策略中心化配置等。

## 4. 关键需求清单（摘录）
- 数据模型：orders, order_media, order_applications, order_status_history（详见 DESIGN）。
- 状态机：NEW → IN_PROGRESS → DONE；NEW/IN_PROGRESS → CANCELED；“申请接单”仅写 application，不改订单状态。
- 回调数据：
  - 频道按钮：act=apply;oid=<id> 与 act=list。
  - 私聊交互：以命令与向导收集并驱动流程。
- 深链：
  - 联系运营：优先 tg://user?id=${OPERATOR_USER_ID}，否则 https://t.me/${OPERATOR_USERNAME}
  - 与 Bot： https://t.me/${BOT_USERNAME}?start=apply_<order_id>
- 安全：白名单鉴权（管理员）、速率限制（5 秒窗口），避免刷操作；不泄露密钥。

## 5. 文本流程图（Textual Flow）
1) 发布与频道首发
- User -> 私聊「📝 发布订单」：逐步收集（标题/内容/金额/媒体）
- Bot：写入 orders（status=NEW, version=0），记录 history(None→NEW)
- Bot：发布频道贴文（含按钮），返回 message_id 并回写订单

2) 申请接单
- Channel User 点击“我要接单” -> Callback(act=apply;oid)
- Bot：速率限制 +（可选）白名单/成员校验 -> 写入 order_applications(PENDING)（唯一键：order_id, applicant_tg_id）
- Bot：回传两段式深链（联系运营 + 与 Bot start=apply_<id>）

3) 审核（管理员）
- Admin -> 私聊「🕒 待审核」：分页列出每个订单的申请人 @username，提供「✅同意」「❌拒绝」
- 同意：校验订单为 NEW -> 更新为 IN_PROGRESS，设置 claimed_by；写 history(NEW→IN_PROGRESS)；编辑频道贴文
- 拒绝：application 标记 REJECTED 并通知申请人

4) 完成
- Admin 或 claimed_by -> 私聊「✅ 已完成」：IN_PROGRESS → DONE；写 history；频道同步

5) 订单列表（私聊）
- User 点击「📋 订单列表」：私聊分页展示 status=NEW 的订单，条目带「查看详情」「申请接单」

## 6. 非功能与技术栈
- 语言与依赖：Python 3.11+，aiogram，SQLAlchemy(Async)，aiosqlite/PostgreSQL，pydantic，pytest+coverage。
- 质量：PEP8、类型注解；关键函数含 docstring；外部 IO try/except 与日志。
- 可观测性：结构化日志与重要事件埋点。

## 7. 环境与运行（摘要）
- .env：
  - BOT_TOKEN, BOT_USERNAME
  - CHANNEL_ID
  - OPERATOR_USER_ID / OPERATOR_USERNAME（两者并存时优先前者）
  - ALLOWED_ADMIN_IDS（逗号分隔）
  - ALLOW_ANYONE_APPLY（true/false）
  - DATABASE_URL（默认 sqlite+aiosqlite:///./orderbot.db）
  - LOG_LEVEL（默认 INFO）
- 本地运行：长轮询；保留 webhook/fastapi 切换位。

## 8. 假设与默认值
- OPERATOR_USER_ID 与 OPERATOR_USERNAME 同时提供时优先使用 OPERATOR_USER_ID。
- ALLOW_ANYONE_APPLY=true 时，任何用户可申请接单；否则仅白名单/管理员可申请。[需确认]
- ALLOWED_ADMIN_IDS 必须配置至少一名管理员以便审批与完成操作。[需确认]
- 订单金额为可选字段，未提供时渲染中不展示金额行。
- 速率限制：同一用户对“我要接单”“同意/拒绝”以及 /update 命令 5 秒仅允许一次；超限提示并记录日志。
- 频道编辑失败重试 3 次（退避 0.5/1/2s）。

## 9. 未决问题与建议默认值（待审批）
1) 申请接单是否要求频道成员身份（除 ALLOW_ANYONE_APPLY 外）？默认：不强制，仅依赖 ALLOW_ANYONE_APPLY。[需确认]
2) 待审核列表分页大小与排序规则？默认：20 条/页，按创建时间倒序。[需确认]
3) 私聊发布流程是否允许一次性命令参数输入（跳过向导）？默认：保留，但优先向导。[需确认]
4) 订单完成是否需要校验由 claimed_by 触发或管理员触发？默认：管理员或 claimed_by 均可。[已采纳]
5) 深链点击后的回执文案与多语言？默认：中文，英文可后续追加 i18n。[需确认]
6) 频道帖子模板的具体格式与占位符（金额/处理人显示规则）？默认：遵循渲染规范，金额缺省则不显示；处理人仅在 IN_PROGRESS/DONE 时显示。[需确认]

## 10. 里程碑与交付
- Architect：输出 DESIGN.md（含 ER/状态机/权限矩阵/渲染/重试）。
- Atomize：输出 TASK.md（P0/P1 任务与 DoD）。
- Approve：等待用户“批准”。
- Automate：生成代码与测试、运行本地测试并产出 ACCEPTANCE.md。
- Assess：覆盖率简报、风险清单与改进路线（Postgres/Webhook/RBAC 等）。

---
本文件用于统一目标与范围，若后续设计与实现与本文不一致，以最新文档为准并回写修订。