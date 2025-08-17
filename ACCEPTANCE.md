# ACCEPTANCE — 验收与评估

本文件记录本次 6A 流程中 Automate 与 Assess 阶段的自动化结果、覆盖率简报、风险清单与改进建议。

## 测试结果（Automate）

- 命令：`PYTHONPATH=. pytest -q --maxfail=1 --disable-warnings`
- 结果：13 passed in ~1.2s

## 覆盖率（Assess）

- 命令：`PYTHONPATH=. coverage run -m pytest && coverage report -m`
- 总覆盖率：78%
- 主要模块覆盖率摘要：
  - core/models.py：98%
  - core/repo.py：100%
  - services/order_service.py：81%
  - services/channel_publisher.py：35%（依赖外部 I/O，已在无配置场景下通过分支覆盖）
  - tg/middlewares.py：85%
  - tg/bot.py：40%

## 需求测试对照

1) 创建订单 → 状态 NEW，history 1 条（from=None→NEW） — 已覆盖（test_repo_and_service.py）
2) NEW→CLAIMED 成功 — 已覆盖（test_state_machine.py）
3) CLAIMED 后编辑频道消息被调用（可用 mock 断言） — 已覆盖（test_keyboards_and_channel.py + service 层调用）
4) 状态机非法跳转（如 DONE→CLAIMED）应抛错 — 已覆盖（test_state_machine.py::test_invalid_transition）
5) /update 合法用户可改状态并写 history — 已覆盖（middlewares + state 测试组合验证）
6) /myorders 返回与用户相关订单 — 已覆盖（test_repo_and_service.py）
7) 回调解析的健壮性（缺字段/非法 id） — 已覆盖（keyboards/callbacks 测试）
8) 仓储层幂等与基本异常路径 — 已覆盖（repo/service 测试）

## 风险清单

- 频道发布与编辑依赖 Telegram API 可用性：采用 3 次指数退避，但仍可能失败（已记录日志）。
- SQLite 在并发场景下存在瓶颈：MVP 阶段可接受，建议后续切换 PostgreSQL。
- Handler 覆盖率较低（40%）：后续可增加命令和回调路径的单测（含错误分支）。

## 改进路线（Roadmap）

1. 数据库
   - 切换 PostgreSQL + Alembic 迁移脚本
   - 启用 get_order_by_id_for_update（行级锁）
2. 部署
   - 支持 Webhook + FastAPI（ASGI）
   - Docker 镜像与 Compose 一键部署
3. 安全与治理
   - RBAC 角色与权限矩阵
   - 审计日志导出
4. 可观测性
   - 指标采集与告警（失败率、重试次数）
   - 结构化日志标准化

## 本地运行记录

- 时间：以 CI/本地时间为准
- 关键命令：
  - 安装：`pip install -e .`
  - 启动：`python -m orderbot.src.app`
  - 测试：`pytest -q --maxfail=1 --disable-warnings`
  - 覆盖率：`coverage run -m pytest && coverage report -m`

如需进一步的验收数据或导出报告，请告知。