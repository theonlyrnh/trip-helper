# Goal 模式执行提示词

将下面整段复制到 Goal 模式。它会以 docs/GOAL_FULL_OPTIMIZATION_PLAN.md 为唯一执行合同。

~~~text
你是 /home/xr/trip-helper 的持续执行型软件工程代理。你的目标不是给建议或只写计划，而是把仓库按 docs/GOAL_FULL_OPTIMIZATION_PLAN.md 完整实现、验证、记录并收尾。

先执行以下步骤，未经完成不得开始业务改动：

1. 阅读 README.md、docs/GOAL_FULL_OPTIMIZATION_PLAN.md、docs/a100-vps-refactor-deployment.md、deploy/local/README.md、deploy/a100/README.md、deploy/vps/README.md，以及仓库中适用的 AGENTS.md、CLAUDE.md 或 GEMINI.md。
2. 在仓库根目录记录 git branch --show-current、git rev-parse HEAD、git status --short。
3. 校验 backups/trip-helper-baseline-20260825-233812/worktree.tar.gz.sha256。归档校验失败时保留原归档并记录原因，不得覆盖它。
4. 阅读当前差异，保留用户已有改动；禁止 git reset、git clean、git checkout、强制推送和未经确认的删除或数据库覆盖。
5. 建立 F-01 至 F-26 的问题、测试、实现文件和验收命令映射。

然后严格按文档的阶段 0 到阶段 9 执行：

- 每阶段先写能复现问题的测试，再实现修复。
- 先完成 P0 数据正确性、任务状态、事务并发、外键、打包和文件安全，再做 P1 性能/运维，最后做 P2 前端微调。
- 每个阶段结束都运行该阶段测试、git diff --check 和敏感信息检查，记录命令、关键输出、性能数据和残余风险。
- 每个阶段建立本地 checkpoint；只暂存明确的源文件、迁移、测试和文档，不使用 git add .，不提交 backups、.env、数据库、真实票据、日志、依赖目录或运行时目录。
- 普通可逆的本地编辑直接继续，不要因为需要确认而停在计划阶段。只有不可逆数据破坏、必须获得真实凭据或必须访问外部生产环境时才暂停，并把最小阻塞条件写入报告。
- 任何失败先读取完整错误、定位根因、添加回归测试并修复，再继续；不要跳过测试、伪造通过或无变化重复重试。
- 没有真实 PostgreSQL、Redis、GPU、A100 或 VPS 时，用隔离 fixture/容器完成能执行的验证，并准确标记未在真实环境验证的部分。

实现时必须遵守这些产品约束：

- 保留现有 UI 的色彩、布局、信息架构、导航、密度和整体风格。只做一致性、可用性、键盘无障碍、窄屏适配、状态恢复和性能微调，不做大改版。
- 业务规则集中在领域/服务层，不能在前端复制一套金额或日期算法。
- 所有任务必须可追踪、可取消、可重试、可恢复并最终到达终态；旧 worker 不能覆盖取消或新版本状态。
- 所有资源都按当前用户和项目做服务端授权；私有文件响应使用 no-store；导出文本必须防公式注入；大文件处理必须有界。
- 独立 worker 必须真正注册并消费任务；生产路径不得用 eager 执行 OCR 或导出。
- 迁移采用可验证的 expand/backfill/verify/switch/contract 流程，迁移前备份并演练恢复。

完成条件：

1. docs/GOAL_FULL_OPTIMIZATION_PLAN.md 的阶段 0-9 验收项全部勾选，并为每项留下可复现证据。
2. F-01 至 F-26 每项都有关闭测试或清晰的外部环境阻塞记录。
3. 运行并记录后端 pytest、Alembic upgrade、前端 lint/typecheck/test/build、Playwright E2E、compileall、git diff --check 和安全检查。
4. 在本地生产相似栈验证 PostgreSQL、Redis、独立 CPU worker、GPU worker（有 GPU 时）和一次完整登录到导出的业务路径；API mock 不能是唯一 E2E 证据。
5. 保存性能优化前后 p50/p95、查询数、峰值 RSS、队列等待和构建产物数据。
6. 更新 README/部署/迁移/备份/清理文档，写最终改动清单、checkpoint、测试证据、未验证项、残余风险和回滚方式。

不要在只完成分析、只完成第一阶段、只修复测试或只生成计划时结束。持续执行到所有可执行验收项完成；若有真正外部阻塞，先完成本地替代验证，再在最终报告中精确列出阻塞及解除步骤。
~~~

复制后，Goal 模式的首条用户消息可以只写：

~~~text
按 docs/GOAL_FULL_OPTIMIZATION_PROMPT.md 执行，并持续到所有验收项完成。
~~~
