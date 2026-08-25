# Trip Helper 全范围优化执行计划

> 版本：1.0
> 建立日期：2026-08-25
> 执行对象：Goal 模式中的持续执行代理
> 当前基线：main 分支，Git HEAD 04a4bc25225e228567c544e2dd81a33d4ca8b45e
> 基线归档：backups/trip-helper-baseline-20260825-233812/worktree.tar.gz

本文件是下一轮夜间开发的执行合同。目标是修复已确认的数据正确性、任务可靠性、数据安全、部署可复现性和响应速度问题，同时保留现有 UI 的色彩、布局密度、导航方式和整体气质。Goal 代理必须按本文实施、验证、记录和回滚，不能只输出计划。

## 1. 完成定义

只有同时满足以下条件，Goal 代理才可以结束：

1. P0、P1 和 P2 阶段的验收项全部完成，或有明确的外部环境阻塞证据、替代测试证据和后续操作记录。
2. 已知的业务正确性、并发、任务状态、文件安全和打包问题都有回归测试或可重复的集成测试。
3. 本地生产相似栈至少完成一次：PostgreSQL、Redis、独立 CPU worker、独立 GPU worker（有 GPU 时）和前端构建验收。
4. 所有测试、类型检查、lint、构建、迁移和安全检查的命令及结果已记录。
5. 前端没有大规模视觉重构；视觉变化仅限于一致性、可用性、无障碍和性能所需的微调。
6. 没有把真实密钥、Cookie、密码、内部地址、数据库、真实票据、日志或本地运行时文件加入 Git。
7. 每个阶段都有可识别的 checkpoint，且能够说明如何回滚到上一阶段或本基线。
8. 最终报告包含改动文件、迁移说明、测试证据、性能前后数据、残余风险和回滚命令。

## 2. 开始前硬性规则

### 2.1 先保护基线

Goal 代理启动后的第一步必须执行并记录：

~~~bash
cd /home/xr/trip-helper
git branch --show-current
git rev-parse HEAD
git status --short
sha256sum -c backups/trip-helper-baseline-20260825-233812/worktree.tar.gz.sha256
~~~

如果校验失败，先复制现有归档到只读位置并记录原因，不得覆盖或重建原归档。当前工作区已经有用户改动，禁止使用 git reset、git clean、git checkout、强制推送或删除用户文件来“整理”工作区。

### 2.2 变更和提交规则

- 先阅读 README、部署文档、本文和所有适用的仓库指令，再编辑。
- 每个阶段先添加能复现问题的测试，再实现修复。
- 保持现有模块边界；只有在打包、事务或可测试性确实需要时才移动模块。
- 不使用 git add .；只暂存明确的源文件、迁移、测试和文档。
- 每个 checkpoint 提交前执行 git diff --check、状态检查和该阶段测试。
- 默认只做本地提交，不执行 git push、远程上传或发布。
- 遇到与本任务无关的用户改动时保留它们；遇到同一文件的冲突时先读取并合并意图。
- 不把基线归档、备份目录、运行时目录加入提交。

### 2.3 外部服务规则

没有真实 PostgreSQL、Redis、GPU、域名或服务器凭据时，使用隔离的本地 fixture、容器或 mock 完成可执行的验证，并明确标记“未在真实环境验证”。不得伪造成功的部署结果，也不得把生产配置写入仓库。

## 3. 当前架构和边界

~~~text
浏览器
  -> VPS/Caddy 或本地 Vite
  -> 同源 /api/v1
  -> FastAPI
       -> PostgreSQL（生产）或 SQLite（本地验收）
       -> 文件存储
       -> Redis + Celery CPU/GPU worker
       -> MinerU/PaddleOCR/Tesseract 适配器
       -> Excel/PDF 导出
~~~

核心代码位置：

| 边界 | 目录或文件 | 责任 |
| --- | --- | --- |
| API | backend/app/api/v1 | 认证、项目、上传、文档、任务、复核、导出、设置 |
| 领域 | backend/app/domain、backend/app/schemas.py | 报销规则、输入契约和派生数据 |
| 数据 | backend/app/infrastructure/db、backend/alembic | 模型、事务、迁移和索引 |
| 队列 | backend/app/workers、backend/app/infrastructure/queue | Celery 入口、任务路由和状态 |
| OCR/存储 | backend/app/infrastructure/ocr、storage | 原件、预览、OCR 和流式读写 |
| 服务 | backend/app/services | 文档、发票、任务、导出、设置和审计 |
| 前端 | frontend/src/features、frontend/src/api | 工作台、状态同步、上传、复核和导出 |
| 部署 | deploy/local、deploy/a100、deploy/vps | 本地生产相似栈、A100 和 VPS |

## 4. 已确认问题清单

以下问题来自当前代码阅读、已有测试和手工探针。Goal 代理必须先为每个 ID 建立回归测试，再关闭问题。

### 4.1 数据正确性和领域规则

| ID | 级别 | 位置 | 现象 | 必须达到的结果 |
| --- | --- | --- | --- | --- |
| F-01 | P0 | backend/app/schemas.py、services/trips.py、domain/reporting/summary.py | 出发日晚于返程日时可以生成 trip_days=-8 和负补助 | API 拒绝非法区间；同日和跨日语义明确并锁定测试；任何汇总不出现负天数或负补助 |
| F-02 | P0 | 报销设置和汇总服务 | 出发日/返程日补助、住宿限额、返程票要求、住宿发票要求已暴露但未参与计算或异常检测 | 设置成为同一套领域规则的唯一来源，并在汇总和异常中生效 |
| F-03 | P0 | backend/app/services/trips.py | daily_allowance=0 会被 or Decimal(180.00) 错误恢复为默认值 | 只有 None 触发默认值；0、负数策略和货币精度有明确校验 |
| F-04 | P0 | backend/app/services/recognition.py、documents.py | 空或全空白 OCR 文本被当作成功，且没有创建可人工录入的票据 | 空 OCR 进入 NEEDS_REVIEW 或等价终态，创建人工复核记录并显示原因 |
| F-05 | P0 | 汇总重建和幂等逻辑 | 票据派生的交通、住宿和汇总需要在重复处理后保持一致 | 以 invoice_id 等稳定键幂等重建，重复任务不产生重复金额或记录 |
| F-06 | P1 | schemas、解析器、异常检测 | 日期推断来源多，但人工确认、低置信度和冲突处理需要统一 | 保留推断来源和置信度；人工确认始终覆盖推断；冲突生成可解释异常 |

### 4.2 任务、事务和数据完整性

| ID | 级别 | 位置 | 现象 | 必须达到的结果 |
| --- | --- | --- | --- | --- |
| F-07 | P0 | backend/app/workers/celery_app.py、workers/tasks.py | 独立 Celery worker 入口没有导入任务，任务注册表实测为空 | 独立 CPU/GPU worker 启动后注册预期任务；有注册表 smoke test |
| F-08 | P0 | services/jobs.py、documents.py、exports.py | 失败时 Export/Document 可能永久停留在 RUNNING/PREPROCESSING | 所有路径都有终态；异常、超时和进程重启可恢复；错误可重试且不重复副作用 |
| F-09 | P0 | services/jobs.py | 取消后已运行 worker 仍可能覆盖 CANCELLED | 状态转换有条件更新或代次令牌；取消是终态，旧 worker 不能回写成功 |
| F-10 | P0 | services/invoices.py、infrastructure/db/models.py | 版本校验不是数据库原子乐观锁；两个旧版本并发更新都成功，后写覆盖先写 | 单条条件 UPDATE/事务保证只有一个旧版本写入成功，另一方得到明确冲突响应 |
| F-11 | P0 | infrastructure/db/session.py | SQLite PRAGMA foreign_keys=0 | SQLite 测试连接和生产迁移都启用外键；删除和孤儿数据行为有测试 |
| F-12 | P0 | backend/pyproject.toml、旧顶层 parsers/services | 新 app 仍依赖旧顶层模块，但 wheel 只打包 app* | 从干净环境构建 wheel 并导入运行；依赖要么正式打包，要么迁移到 app 内 |
| F-13 | P1 | alembic、models | 索引、唯一约束和迁移回滚边界不完整 | 新库和现有库均可升级；关键唯一键、外键、查询索引在迁移中声明 |

### 4.3 文件、OCR 和导出

| ID | 级别 | 位置 | 现象 | 必须达到的结果 |
| --- | --- | --- | --- | --- |
| F-14 | P0 | services/exports.py | XLSX 用户内容未转义，可能形成公式注入 | 对以 =、+、-、@ 开头的文本进行安全转义，同时保留应为数字的数值类型 |
| F-15 | P1 | services/exports.py | PDF 默认字体可能无法显示中文，内容只有摘要 | 使用可配置且可验证的中文字体回退/嵌入；报告包含用户需要的明细、汇总和异常 |
| F-16 | P1 | services/exports.py、任务清理 | expires_at 没有实际设置或回收，导出文件无限增长 | 生成时设置过期时间；有清理任务、保留策略、下载竞态保护和磁盘指标 |
| F-17 | P0 | API 文件响应 | 文档、预览、OCR、导出缺少明确 Cache-Control: no-store | 私有内容默认 no-store，并测试响应头、Content-Disposition 和授权 |
| F-18 | P1 | OCR 上传链路 | OCR Base64 一次性读入整张图片；大 PDF 页面/像素限制不完整 | 上传、解码、OCR 和预览使用分块/流式或有界缓冲；页数、像素、超时和并发有统一上限 |
| F-19 | P1 | storage、API | 文件名、路径和错误信息存在潜在路径泄露/资源滥用面 | 只使用随机 storage key；原始文件名仅作显示；所有资源按用户/项目授权过滤 |

### 4.4 性能、认证、运维和前端

| ID | 级别 | 位置 | 现象 | 必须达到的结果 |
| --- | --- | --- | --- | --- |
| F-20 | P1 | documents API、dashboard service | 文档列表有 N+1 查询且无分页 | 服务端分页或游标分页，批量加载关联数据，返回稳定排序和总数/游标 |
| F-21 | P1 | deploy/a100 | 隧道部署使用 eager task，OCR/导出会占用 API 进程 | 生产路径使用独立 CPU/GPU worker；eager 仅限明确标记的本机验收 |
| F-22 | P1 | auth、rate_limit | 没有完整管理员授权、密码修改/找回、全设备会话撤销；限速器是单进程内存实现 | 角色和权限有明确矩阵；密码和会话生命周期可管理；多进程限速使用 Redis 或有界持久后端 |
| F-23 | P1 | health API、logging | /health 只有静态 liveness，难以判断 DB、Redis、存储和 OCR 是否可用 | 分离 liveness/readiness；不泄露凭据；日志有 request/job correlation id 和可观测指标 |
| F-24 | P2 | frontend/src/features、app/query.ts | 上传、轮询、错误恢复和缓存失效需要覆盖刷新、取消和失败重试 | 任务状态可恢复；轮询退避且可取消；写入后只失效必要查询；错误可操作 |
| F-25 | P2 | frontend/src/index.css、各工作台组件 | 当前 UI 风格喜欢，但大规模重构会引入回归 | 保留现有色彩、布局、密度、圆角和导航；只做一致性、键盘操作、响应式和性能微调 |
| F-26 | P1 | 全部测试、部署脚本 | 测试主要使用 SQLite、eager Celery 和 mock API，未覆盖真实 PostgreSQL、Redis、独立 worker、并发和部署 | 增加分层测试矩阵，并将生产相似栈作为发布门槛 |

## 5. 目标和非目标

### 5.1 目标

- 先保证金额、日期、任务状态和权限正确，再做性能优化。
- 让 API 进程只负责请求编排，把 OCR、解析和导出放到可恢复的后台队列。
- 让大文件处理的内存占用由文件大小降为有界分块，列表查询由 N+1 变为分页批量查询。
- 让数据库约束、迁移和事务成为业务不变量的最后防线。
- 让失败可以诊断、重试、取消、恢复和回滚。
- 让前端在保留现有风格的前提下减少重复请求、全页刷新和状态丢失。

### 5.2 非目标

- 不更换 React、FastAPI、Celery、PostgreSQL、Redis 或既有 OCR 适配器，除非有可量化的阻塞证据。
- 不把现有工作台改成营销页、卡片堆叠、全新配色或全新导航。
- 不在没有数据迁移方案、备份和回滚演练时删除旧字段或重写数据库。
- 不把真实 A100/VPS 地址、凭据或票据复制到仓库。
- 不用微优化掩盖未修复的 P0 数据错误。

## 6. 性能和质量目标

Goal 代理必须先在本地生产相似栈建立基线，再记录优化后的同一组指标。硬件差异较大时记录环境、样本量和相对改善，不得只给主观描述。

| 指标 | 目标 |
| --- | --- |
| 文档列表 API | 1000 份文档场景下分页查询 p95 不超过 500 ms，查询次数不随文档数线性增长 |
| 工作台摘要 API | p95 不超过 800 ms；关联数据批量读取；无重复全表扫描 |
| 上传响应 | 文件传输完成后尽快返回任务 ID；API 不把完整文件或 Base64 长期留在内存 |
| OCR/导出 | API 进程不执行生产 OCR/导出；任务有超时、重试和终态 |
| 前端轮询 | 有退避、可取消、刷新后可恢复；不产生重复并发请求 |
| 数据一致性 | 日期、金额、汇总和状态不变量有自动化测试；并发旧版本最多一个成功 |
| 安全响应 | 私有文件 no-store；无路径泄露、公式注入、越权下载和跨项目访问 |
| 发布可靠性 | 干净环境能安装、迁移、启动、导入任务并完成最小端到端流程 |

## 7. 分阶段执行顺序

不得跳过 P0，也不得在 P0 未通过时进行 UI 重构。

| 阶段 | 优先级 | 主要产出 | 依赖 |
| --- | --- | --- | --- |
| 0. 基线和契约 | P0 | 快照校验、测试矩阵、领域不变量清单 | 无 |
| 1. 可安装性和数据库基础 | P0 | 可导入 wheel、任务注册、迁移、外键和索引 | 0 |
| 2. 领域正确性 | P0 | 日期、补助、设置、OCR 人工复核和幂等汇总 | 1 |
| 3. 任务生命周期 | P0 | 终态、取消、重试、恢复和队列路由 | 1、2 |
| 4. 事务和并发 | P0 | 原子乐观锁、约束、授权事务和并发测试 | 1、2 |
| 5. 文件、OCR 和导出 | P0/P1 | 流式处理、限制、缓存头、XLSX/PDF 安全和清理 | 2、3、4 |
| 6. 性能和资源 | P1 | N+1 消除、分页、索引、队列隔离和基准 | 3、5 |
| 7. 认证、健康和可观测性 | P1 | 权限、会话、限速、readiness、日志和指标 | 3、4 |
| 8. 前端工作台微调 | P2 | 状态恢复、错误处理、无障碍和性能微调 | 2、3、5、7 |
| 9. 发布和回滚演练 | P0 | 全套门禁、迁移/备份恢复、部署证据和最终报告 | 1-8 |

## 8. 阶段实施说明

### 8.1 阶段 0：基线和契约

涉及位置：根目录、docs、tests、backend/tests、frontend/tests。

执行：

1. 校验第 2.1 节命令，并把输出保存到本地阶段记录。
2. 阅读 README、docs/a100-vps-refactor-deployment.md、deploy/local/README.md、deploy/a100/README.md 和 deploy/vps/README.md。
3. 建立问题 ID 到测试文件、实现文件和验收命令的映射。
4. 先写日期、金额、状态、授权、并发和文件安全不变量测试。
5. 记录当前 API、列表、上传和导出基线延迟、查询数、峰值内存和构建产物大小。

验收：

- 快照校验通过。
- 每个 F-01 至 F-26 都有负责人模块、测试入口和完成判据。
- 基线指标可以在同一环境重复测量。

checkpoint：只提交测试契约、基线记录和文档，不提交运行时文件。

### 8.2 阶段 1：可安装性、任务注册和数据库基础

主要文件：backend/pyproject.toml、backend/app/workers/celery_app.py、backend/app/workers/tasks.py、backend/app/infrastructure/db/session.py、backend/app/infrastructure/db/models.py、backend/alembic/。

执行：

1. 让干净虚拟环境能够构建 wheel 并导入 app.main、Celery 入口和所有任务模块；处理旧顶层 parsers/services 的打包边界。
2. 让 Celery 入口显式 include 或 autodiscover 任务，分别验证 cpu、gpu、default 队列的注册结果和任务路由。
3. 为 SQLite 连接启用外键，并为 PostgreSQL 迁移补齐外键、唯一键、状态字段和列表查询索引。
4. 检查迁移在空库和已有测试库上的 upgrade；任何非可逆迁移都必须先备份并记录恢复方案。
5. 添加导入 smoke test、迁移 smoke test 和独立 worker 启动测试。

验收：

- 从全新环境安装后，Celery inspect/注册表能看到预期任务。
- 空数据库和现有 fixture 均可迁移，外键违规会失败。
- wheel 不依赖工作目录偶然存在的旧模块。

checkpoint：提交消息格式为 checkpoint(opt): packaging-and-schema；提交前运行干净安装、迁移和 worker smoke test。

### 8.3 阶段 2：领域正确性

主要文件：backend/app/schemas.py、backend/app/services/trips.py、backend/app/domain/reporting/summary.py、backend/app/services/recognition.py、backend/app/services/documents.py、相关解析器和设置 API。

执行：

1. 明确日期语义：出发日晚于返程日返回可定位的 4xx；同日是否算 1 天必须由现有业务契约决定并写测试；日期计算使用时区无关的 date 运算。
2. 修复默认值判断，区分 None、0、负数和空字符串；金额统一 Decimal、量化和舍入。
3. 将出发日/返程日补助、住宿上限、返程票要求、住宿发票要求纳入领域服务，不在 API 或前端重复实现规则。
4. 给每项推断保存来源、置信度和人工覆盖状态；冲突或低置信度时生成可操作异常。
5. 空 OCR、解析失败和不支持格式都建立人工复核记录，不能伪装为成功。
6. 以稳定键重建交通、住宿和汇总，重复上传、重试和人工编辑都保持幂等。

验收：

- 反向日期、零补助、边界金额、跨年日期、空 OCR 和重复任务测试通过。
- 汇总结果能解释每一项金额和设置来源。
- 旧回归测试不退化，API 错误格式稳定。

checkpoint：提交消息格式为 checkpoint(opt): domain-correctness。

### 8.4 阶段 3：任务生命周期和队列可靠性

主要文件：backend/app/services/jobs.py、backend/app/workers/tasks.py、backend/app/api/v1/jobs.py、documents.py、exports.py、deploy/local、deploy/a100。

执行：

1. 把任务状态转换集中成有限状态机，定义允许转换、终态和错误载荷。
2. 用数据库条件更新或版本/代次令牌保护 RUNNING、SUCCEEDED、FAILED、CANCELLED 和 RETRYING 的竞争写入。
3. 在任务 finally 路径写入失败终态；将超时、异常、撤销和进程重启分别测试。
4. 任务拆成可重试的幂等步骤；外部 OCR 和导出副作用写入幂等键，避免重试生成重复文件。
5. 取消请求先持久化，再让 worker 检查取消令牌；旧 worker 不得把 CANCELLED 改回成功。
6. 生产部署关闭 eager，CPU、GPU 和 default 队列由独立 worker 消费；本机 eager 只能由显式配置启用。
7. 为孤立 RUNNING 任务增加启动恢复/看门狗策略，并保留人工重试入口。

验收：

- 任务成功、失败、重试、超时、取消、worker 重启和重复投递都有自动化测试。
- 任何任务最终都会到终态或可诊断的 RETRYING，不会无限停在 PREPROCESSING。
- 独立 worker 可处理真实队列消息，API 不执行重任务。

checkpoint：提交消息格式为 checkpoint(opt): job-lifecycle。

### 8.5 阶段 4：事务、并发和授权

主要文件：backend/app/services/invoices.py、backend/app/api/deps.py、backend/app/infrastructure/db/session.py、models、alembic、相关 API 测试。

执行：

1. 对发票更新使用单条条件 UPDATE：匹配 id、所属项目/用户和旧 version，成功后 version + 1；rowcount 为 0 时返回冲突。
2. 在事务边界内更新发票、异常解决状态和派生汇总；异常时整体回滚。
3. 加入唯一约束、外键、检查约束和必要索引；SQLite 与 PostgreSQL 的行为分别验证。
4. 所有资源查询先做用户/项目所有权过滤，再执行读取或写入；不能依赖前端隐藏按钮。
5. 编写两个并发旧版本写入、跨项目访问、删除父记录和事务失败恢复测试。

验收：

- 并发更新只有一个成功，另一个收到稳定的 409/等价冲突。
- 数据库和服务层都能阻止孤儿、重复派生记录和越权资源。
- 事务失败后金额、版本、异常和任务状态保持原值。

checkpoint：提交消息格式为 checkpoint(opt): transactional-integrity。

### 8.6 阶段 5：文件、OCR、预览和导出

主要文件：backend/app/infrastructure/storage、backend/app/infrastructure/ocr、backend/app/services/recognition.py、documents.py、exports.py、文件响应 API。

执行：

1. 上传使用分块写入临时对象、SHA-256、文件签名验证和原子落盘；限制文件大小、PDF 页数、图像像素、解码时间和 OCR 超时。
2. OCR 适配器使用有界缓冲或临时文件，禁止把整张图片 Base64 长期存于 API 进程；远程 provider 设连接/读取超时和重试上限。
3. 空 OCR、低置信度和不支持格式进入人工复核，并保留原文、provider、耗时和错误原因。
4. Excel 对用户文本做公式注入转义；测试公式前缀、Unicode、超长文本和数字/日期类型。
5. PDF 使用可配置字体资源并在 CI/fixture 中验证中文可见；报告包含明细、汇总、异常、生成时间和数据范围。
6. 所有私有文件响应设置 Cache-Control: no-store、合理的 Content-Type、Content-Disposition 和范围请求策略；授权检查不能被缓存绕过。
7. 导出记录 expires_at，增加安全的清理任务和保留策略；清理不能删除正在下载或刚生成的文件。
8. storage key 只使用随机标识；错误和日志不回显宿主机绝对路径。

验收：

- 大文件和恶意边界 fixture 不造成无界内存或超时失控。
- 空 OCR 可在前端人工录入并继续汇总。
- XLSX 中任何用户文本都不会变成公式；中文 PDF 可检索或至少正确显示。
- 过期导出可回收，未授权用户无法读取任何文件。

checkpoint：提交消息格式为 checkpoint(opt): file-ocr-export。

### 8.7 阶段 6：查询、缓存和资源性能

主要文件：backend/app/services/dashboard.py、documents.py、trips.py、models、alembic、frontend/src/api、frontend/src/app/query.ts。

执行：

1. 对文档、票据、异常、导出和工作台列表增加稳定排序的服务端分页或游标分页；明确 page size 上限。
2. 用批量查询、select-in/join-load 或等价方式消除 N+1；用查询计数测试锁定上限。
3. 根据 EXPLAIN/查询基准增加最小必要索引，避免无证据的大量索引。
4. 只缓存非敏感、可失效的元数据；文档原文、预览、OCR 和导出默认不缓存。
5. 前端写入后精确失效相关查询，轮询采用退避、可见性暂停、AbortController 和卸载清理。
6. 对上传、OCR、PDF 渲染和导出设置并发、队列长度、超时和磁盘配额，记录峰值内存。
7. 在本地生产相似栈跑固定数据集基准，保存 p50/p95、查询数、RSS、队列等待和吞吐。

验收：

- F-20 的查询数不随列表长度线性增长。
- 目标指标达到第 6 节阈值，或相对基线有可解释的改善。
- 大文件和高并发时 API 仍能处理健康检查和轻量请求。

checkpoint：提交消息格式为 checkpoint(opt): performance。

### 8.8 阶段 7：认证、健康检查和可观测性

主要文件：backend/app/api/v1/auth.py、core/security.py、core/rate_limit.py、api/v1/health.py、core/logging.py、audit.py、deploy 脚本。

执行：

1. 定义角色和权限矩阵，覆盖管理员、普通用户、项目所有者和资源读取范围。
2. 增加改密、会话列表/撤销、全设备撤销和必要的找回流程；敏感操作写审计事件。
3. 将登录限速放到 Redis 或其他共享后端，内存实现只作为明确的单进程开发回退；密码比较和错误响应不泄露账号存在性。
4. 分离 /health/live 和 /health/ready；readiness 检查数据库、队列、存储和启用的 OCR provider，响应不返回连接串或密钥。
5. 为请求、任务、导出和 OCR 记录 correlation id、结构化事件、耗时、重试次数和失败类别；敏感字段打码。
6. 文件、文档、预览、OCR 和导出接口统一 no-store；检查 Cookie、CSRF、CORS、Host 校验和安全响应头。
7. 更新 deploy/local、deploy/a100、deploy/vps 的启动、停止、迁移、日志、备份和最小权限说明。

验收：

- 第二用户不能读取或修改第一用户资源。
- 会话撤销立即生效，限速跨进程有效，readiness 能区分依赖故障。
- 日志足以定位一次上传到导出的完整链路，但不含秘密和原文。

checkpoint：提交消息格式为 checkpoint(opt): auth-observability。

### 8.9 阶段 8：前端工作台微调

主要文件：frontend/src/features、frontend/src/api、frontend/src/app/query.ts、frontend/src/components/AppShell.tsx、frontend/src/index.css。

执行：

1. 维持现有颜色、字体层级、间距、侧栏/顶部导航、表格密度、按钮语义和圆角风格；先建立桌面与移动截图基线。
2. 处理登录过期、网络断开、任务失败、取消、刷新恢复、空 OCR 和导出过期等状态；错误信息应能指导下一步动作。
3. 上传支持进度、取消、重复选择保护和失败重试；目录相对路径保留但不把物理路径发送给 API。
4. 任务轮询只针对当前项目/任务，带退避和取消；路由切换或组件卸载时清理请求。
5. 复核保存使用服务端版本；冲突时展示重新加载/合并入口，不能静默覆盖。
6. 只在数据量确实需要时引入虚拟列表或渐进渲染；确保表格、抽屉、弹窗在窄屏不溢出。
7. 补齐键盘焦点、标签、错误关联、对比度和 reduced-motion；不新增与现有风格冲突的装饰性组件。

验收：

- Playwright 在桌面和移动视口覆盖登录、上传、失败复核、并发冲突、导出和退出。
- 截图对比确认没有大改版、遮挡、文字溢出或布局抖动。
- Vitest、TypeScript、ESLint 和 build 全部通过。

checkpoint：提交消息格式为 checkpoint(opt): workspace-polish。

### 8.10 阶段 9：发布、备份和回滚演练

主要文件：README.md、docs、deploy、scripts、CI 配置（如已有）。

执行：

1. 在全新虚拟环境构建 backend wheel，安装后只从已安装包启动 API 和 worker。
2. 使用 PostgreSQL、Redis 和独立 worker 完成迁移、登录、创建项目、上传、OCR、人工复核、汇总、Excel/PDF 导出、下载和退出。
3. 重启 API、CPU worker 和 GPU worker，验证任务恢复、取消和重试。
4. 对数据库和文件卷做加密备份；在隔离目录执行恢复演练，核对文档数、金额、异常和导出。
5. 执行完整门禁命令，保存输出和环境信息；生产 A100/VPS 无法访问时记录精确缺失项。
6. 更新部署文档、环境变量模板、迁移顺序、清理策略、监控告警和回滚命令。

验收：

- 全套门禁通过，或每个未通过项都有根因、复现命令和修复计划。
- 至少完成一次“升级失败后回到上一 checkpoint”的演练。
- 发布包、数据库迁移和运行时配置可以由另一位工程师按文档复现。

checkpoint：提交消息格式为 checkpoint(opt): release-readiness。完成后才可结束 Goal。

## 9. 测试门禁

每个阶段按风险运行最小测试；阶段 9 运行全部测试。命令以仓库当前脚本为准，若路径或工具发生变化，先更新文档再执行。

~~~bash
PYTHONPATH=backend .venv/bin/python -m pytest tests backend/tests -q
.venv/bin/alembic -c backend/alembic.ini upgrade head
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
python -m compileall backend/app
python /home/xr/.agents/skills/standardized-ai-development/scripts/ai_dev_safety_check.py .
git diff --check
~~~

应补充的测试层：

| 层级 | 必须覆盖 |
| --- | --- |
| 单元 | 日期、Decimal、设置、解析、异常指纹、状态转换、公式转义 |
| API 集成 | 认证、所有权、上传限制、响应头、分页、冲突和错误格式 |
| 数据库 | SQLite 外键、PostgreSQL 迁移、唯一键、事务回滚和索引 |
| 队列 | 独立 worker 注册、路由、重试、取消、幂等和重启恢复 |
| 文件/OCR | 大小/页数/像素边界、空 OCR、中文 PDF、过期清理和流式响应 |
| 并发 | 两个旧版本写入、重复任务、取消与完成竞争、跨项目访问 |
| 前端 | 状态恢复、轮询退避、上传取消、冲突、窄屏和键盘操作 |
| 端到端 | 本地生产相似栈的完整业务路径，不使用全量 API mock |
| 性能 | 固定数据集的 p50/p95、查询计数、RSS、队列等待和导出吞吐 |

## 10. 数据迁移和回滚策略

1. 迁移遵循 expand -> backfill -> verify -> switch -> contract；先添加兼容字段和索引，再切换读写，最后删除旧结构。
2. 每次生产迁移前备份数据库和文件卷，并记录 schema revision、备份校验和恢复耗时。
3. PostgreSQL 大索引按线上可接受方式创建；SQLite 迁移必须在副本上验证外键和数据量。
4. 迁移脚本不得静默丢弃用户字段、原件、OCR 原文或审计记录；无法自动迁移时显式失败。
5. 应用回滚优先使用上一 checkpoint；数据库回滚使用兼容的 down migration 或从备份恢复，不能只回滚代码。
6. 导出、OCR 和队列切换使用环境开关或版本兼容期，避免新旧 worker 同时写入不兼容状态。

## 11. UI 保持约束

- 复用现有 CSS 变量、颜色、字体、间距、表格和工作台组件。
- 不更换品牌色、主导航结构、页面信息架构或核心交互顺序。
- 不新增大型 hero、营销式卡片堆叠、装饰性渐变/光斑或与业务无关的插画。
- 优先改进加载状态、错误状态、空状态、键盘操作、窄屏布局和长文本处理。
- 所有视觉改动都要在桌面和移动截图中检查，确认文字不重叠、不溢出、不遮挡任务状态。

## 12. 敏感文件和提交清单

以下路径永远不得提交或上传：

~~~text
.env
deploy/*/.env*
*.db
*.sqlite*
.local-web-runtime/
data/
fapiao/
logs/
*.log
.venv/
frontend/node_modules/
.tmp-pi-0791/
backups/
私钥、Cookie、密码、API key、token、真实内部地址
~~~

提交前至少执行：

~~~bash
git status --short
git diff --stat
git diff --check
git diff --cached --name-only
python /home/xr/.agents/skills/standardized-ai-development/scripts/ai_dev_safety_check.py .
~~~

发现真实凭据时，停止发布流程，隔离并轮换凭据；不要只从当前文件删除。

## 13. 失败处理和停止条件

- 命令失败：保存完整输出，定位到最小复现，先修根因，再重跑；不要反复盲目重试。
- 测试失败：新增回归测试或修复实现后继续同一阶段，不能用跳过测试代替修复。
- 迁移失败：停止写入，保留数据库副本和日志，验证恢复后再继续。
- 外部依赖不可用：用本地 fixture 完成代码和契约验证，并在最终报告列出未验证的真实环境项。
- 用户已有改动与本阶段冲突：保留原意，拆分提交或记录冲突；禁止回滚用户改动。
- 只有在数据将被不可逆破坏、凭据需要用户提供或外部部署需要明确批准时，才暂停并把阻塞条件写入报告。

## 14. Goal 执行记录

Goal 代理应在每阶段完成后把日期、commit、测试命令、结果和残余风险写入本节或同目录的阶段日志：

- [x] 阶段 0：基线和契约（证据：`docs/optimization-evidence.md` Stage 0/F-ID mapping）
- [x] 阶段 1：可安装性、任务注册和数据库基础（wheel、Celery startup、Alembic smoke）
- [x] 阶段 2：领域正确性（49 项后端回归与日期/金额/OCR/幂等契约）
- [x] 阶段 3：任务生命周期和队列可靠性（终态、取消、重试、GPU handoff）
- [x] 阶段 4：事务、并发和授权（原子版本、外键、所有权和会话 API）
- [x] 阶段 5：文件、OCR、预览和导出（流式响应、no-store、XLSX/PDF/清理）
- [x] 阶段 6：查询、缓存和资源性能（分页、批量序列化、固定数据集 p50/p95）
- [x] 阶段 7：认证、健康检查和可观测性（Redis limiter/fallback、readiness、request id）
- [x] 阶段 8：前端工作台微调（退避/可取消轮询、分页加载、lint/typecheck/test/build/E2E）
- [x] 阶段 9：发布、备份和回滚演练（wheel/迁移/安全门禁；PostgreSQL/Redis 外部阻塞已记录）

本地 checkpoint：`33950fa`（backend-contracts）、`7e7e7e7`
（release-readiness）、`5570628`（workspace-polish）、`2f9e7dd`
（lifecycle-contracts）。这些提交仅在本地，
不执行 push；未相关的根目录用户改动继续保留在工作区。

每个勾选项必须附可复现证据。没有证据时保持未完成。

## 15. 最终报告格式

Goal 结束时输出并保存：

1. 按阶段列出的改动文件和 checkpoint。
2. 每个 F-ID 的关闭证据和对应测试。
3. 全部门禁命令及关键输出。
4. 性能基线与优化后对比。
5. 迁移、备份、部署和回滚步骤。
6. 未在真实 A100/VPS 验证的项目及风险。
7. 不包含任何真实秘密的下一步操作清单。
