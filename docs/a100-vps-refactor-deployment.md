# Trip Helper A100 + VPS 部署基线

本文是当前 Web 重构后的部署与验收基线。用户级 SSH 反向隧道仅作为本地验收 fixture，不使用 Docker、Compose、A100 sudo 或 WireGuard；生产路径使用下文的 PostgreSQL/Redis 与独立 systemd worker。

## 目标架构

```text
任意浏览器
  -> https://APP_DOMAIN
  -> VPS: Caddy / TLS / React 静态文件 / 无缓冲反向代理
  -> VPS: 127.0.0.1:19829 SSH 反向隧道
  -> A100: 127.0.0.1:18001 FastAPI / SQLite / MinerU / 文件存储
```

边界不可变：

1. A100 是 API、SQLite 数据、计算、OCR、原件和导出的唯一后端；A100 不公开 HTTP API。
2. VPS 只公开 TCP `80/443`，只转发 API 字节流，不保存票据。
3. A100 API 与 MinerU 均只绑定 A100 回环地址；SSH 反向隧道仅绑定 VPS 回环地址 `127.0.0.1:19829`。
4. 浏览器只识别 `APP_DOMAIN`，所有请求使用同源 `/api/v1`，不直连 A100。
5. 域名、IP、私钥、数据库密码、会话密钥和真实 OCR 配置不写入仓库。

## 已实现模块

```text
backend/
├── app/
│   ├── api/v1/             # 认证、项目、上传、任务、复核、导出、设置
│   ├── core/               # 类型化配置、Argon2、CSRF、日志和登录限速
│   ├── domain/reporting/   # 纯报销汇总规则
│   ├── infrastructure/     # PostgreSQL/Storage/Celery/OCR 适配器
│   ├── services/           # 解析、派生视图、异常、导出
│   └── workers/            # CPU 与 GPU Celery 入口
├── alembic/                # PostgreSQL schema migration
└── pyproject.toml
frontend/
├── src/features/           # 登录、项目、上传、处理、复核、导出、设置
└── src/api/                # 唯一同源 API client 与 DTO 映射
deploy/
├── local/                  # 原生本机 PostgreSQL/Redis/Celery 运行方式
├── a100/                   # A100 安装脚本、env 模板、systemd 单元
└── vps/                    # Caddy、WireGuard、TLS 静态发布脚本
```

旧 `backend/main.py`、`backend/routers/` 和 Windows 文件夹扫描模块仅保留为旧回归行为参考。当前 A100 用户级入口为 `deploy/a100/tunnel.sh`，可选原生 systemd 入口为 `app.main:app`；旧路由不能作为远程版本入口。

## 业务契约

以下语义由新领域层和旧回归测试共同锁定：

1. 仅 `THIS_TRIP` 且 `include_in_summary=true` 的票据进入本次报销汇总。
2. 金额优先级为 `confirmed_amount > total_amount > 0`；未确认且大于 `100000` 的 OCR 金额不得进入汇总。
3. 订单截图、酒店预订截图、辅助凭证默认不计入金额。
4. `DAILY` 项目不计算差旅补助；其他项目补助为 `trip_days * daily_allowance`。
5. OCR 原文存于 `ocr_runs`，人工编辑只更新 `invoices`，不会覆盖 OCR 原文。
6. 交通片段、住宿记录和汇总由票据幂等重建；`invoice_id` 具有唯一约束。
7. 日期推断优先级为城际交通、住宿、项目输入日期、项目标签/名称和浏览器相对目录日期、票据业务日期、开票日期；人工确认日期始终覆盖推断结果。
8. PDF 原生文字优先；高铁 PDF 保留 PyMuPDF words 坐标解析。
9. 图片识别按 PaddleOCR、可选 MinerU、本地受控远程视觉模型、原生 Tesseract 中文/英文依次回退；远程密钥只存在于服务端环境文件。
10. 异常使用规则指纹，人工已解决/忽略决定保留；已经不成立的开放异常标记为自动关闭。
11. Excel 与 PDF 由后台任务生成，下载经过当前用户授权，不返回宿主机路径。

## Web API 与隐私

- `POST /api/v1/auth/bootstrap` 只在不存在用户时可创建首个管理员；SSH 隧道和原生生产模式均必须同时提供 `BOOTSTRAP_TOKEN`。
- `POST /api/v1/auth/login`、`POST /api/v1/auth/logout`、`GET /api/v1/auth/me` 使用 HttpOnly 会话 Cookie。
- 所有写请求需要 `X-CSRF-Token`；登录和当前会话响应返回该 token。
- `POST /api/v1/trips/{id}/uploads` 接收单文件 multipart 流，浏览器目录上传只能提交相对路径。
- 文档响应只包含资源 ID、原始文件名、相对目录、哈希、状态和授权资源接口，不返回物理路径。
- 文件、预览、OCR 原文和导出通过已鉴权的流式接口返回。
- `jobs` 表是任务状态真相源，状态为 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 或 `RETRYING`。
- CPU worker 处理预览、原生文本、解析、分析和导出；GPU worker 仅消费 `gpu` 队列且固定并发 `1`。

上传安全顺序：认证和项目所有权 -> 分块写入临时对象与 SHA-256 -> 文件签名验证 -> PDF 页数/图像像素限制 -> 随机 storage key 落盘和元数据事务 -> 创建后台任务。上传请求不会将完整文件读入内存。

## 本机验收优先

在没有域名、VPS 或 A100 参数前，先按根目录 [README](../README.md) 运行本机浏览器验收。该环境用 SQLite 和 eager 任务替代原生 PostgreSQL/Redis worker，仅用于 UI 与接口验收，不是生产拓扑。

完整原生本地栈：

```bash
cp deploy/local/.env.local.example deploy/local/.env.local
deploy/local/init-postgres.sh
deploy/local/start.sh bootstrap
deploy/local/start.sh api
deploy/local/start.sh worker-cpu
deploy/local/start.sh worker-gpu  # 仅在有 NVIDIA 驱动时
deploy/local/start.sh frontend
```

本机验收项：登录、创建项目、多文件与目录上传、刷新后任务恢复、PDF 预览、人工确认金额、异常解决/忽略、异步 Excel/PDF 导出、退出登录和第二用户越权拒绝。

## A100 用户级 SSH 隧道

当前 A100 已有用户级 MinerU 3.3.1，监听 `127.0.0.1:8888`，其 `/health` 与
`/file_parse` 已验证可用。Trip Helper 使用同一用户账户启动，不改变 MinerU
进程，也不要求 A100 管理员权限：

```bash
deploy/a100/tunnel.sh bootstrap
deploy/a100/tunnel.sh setup
deploy/a100/tunnel.sh start
deploy/a100/tunnel.sh create-admin --email ADMIN_EMAIL
deploy/a100/tunnel.sh test
```

首次 `start` 会生成被 Git 忽略且权限为 `0600` 的
`deploy/a100/.env.tunnel`。其中的 SQLite 数据库、上传原件、预览、OCR 原文、
导出、日志和 PID 均保存在 A100 用户目录 `~/.local/share/trip-helper`。API
固定监听 `127.0.0.1:18001`，看门狗使用
`ssh -R 127.0.0.1:19829:127.0.0.1:18001 zhijiage` 自动重连。

用户级隧道模式明确标记为本地验收 fixture：使用 `TASKS_EAGER=true`，上传处理、
MinerU OCR、分析和导出均在 A100 API 进程内执行。它保留 HTTPS Cookie、严格域名
校验、CSRF 和首管理员令牌；SQLite 只在 A100 本地访问。生产路径不得沿用该模式，
必须使用下方 PostgreSQL、Redis 以及独立 CPU/GPU worker 的 native systemd 单元。

VPS 的 `deploy/vps/.env` 设为：

```dotenv
API_UPSTREAM=127.0.0.1:19829
```

之后由 VPS 管理员手动运行 `sudo deploy/vps/setup-caddy.sh`。Caddy 只向
VPS 回环地址代理 `/api/*`，上传数据通过 SSH 隧道直达 A100。

## 可选原生 A100 服务

前置条件：实际 A100 Linux 宿主机、PID 1 为 systemd、Python 3.11+、PostgreSQL、Redis、WireGuard、NVIDIA 驱动与可用 `nvidia-smi`。A100 需要能主动连接 `VPS_PUBLIC_IP:51820/udp`，持久化目录建议为加密磁盘上的 `/srv/trip-helper`。不在没有 `NET_ADMIN` 能力的开发容器中执行生产安装脚本；该环境不能创建 WireGuard 接口或托管 systemd 服务。

真实配置只放在 `/etc/trip-helper/trip-helper.env`，从 `deploy/a100/.env.production.example` 复制。关键值：

```dotenv
APP_ENV=production
APP_DOMAIN=APP_DOMAIN
DATABASE_URL=postgresql+psycopg://trip_helper:POSTGRES_PASSWORD@127.0.0.1:5432/trip_helper
REDIS_URL=redis://127.0.0.1:6379/0
STORAGE_ROOT=/srv/trip-helper
SESSION_SECRET=SESSION_SECRET
COOKIE_SECURE=true
PADDLEOCR_API_URL=http://127.0.0.1:8118/v1
TESSERACT_FALLBACK_ENABLED=true
TESSERACT_LANGUAGES=chi_sim+eng
# Native MinerU 3.3.1 service (multipart /file_parse, no Docker required)
MINERU_API_URL=http://127.0.0.1:8888
MINERU_ENABLED=true
OCR_PROVIDER=mineru
```

安装流程：

```bash
sudo deploy/a100/setup-a100.sh --install-os-deps
sudo systemctl status trip-helper-api trip-helper-worker-cpu trip-helper-worker-gpu
```

该脚本创建受限服务用户、Python 虚拟环境、PostgreSQL 角色/数据库、回环 Redis、Alembic schema 和以下 systemd 单元：

- `trip-helper-api.service`: `uvicorn app.main:app --host 10.66.0.2 --port 8000`
- `trip-helper-worker-cpu.service`: `celery ... -Q cpu,default --concurrency=2`
- `trip-helper-worker-gpu.service`: `celery ... -Q gpu --concurrency=1`
- `trip-helper-ocr.service`: 仅在填入经过验证的回环 OCR 命令后启用

当前 A100 验收时 `127.0.0.1:8888` 已运行 MinerU 3.3.1 FastAPI 服务，
`/health` 与 `/file_parse` 可调用；`127.0.0.1:8118` 尚未运行
PaddleOCR-VL。应用通过 `MINERU_API_URL` 适配该接口，Tesseract 作为最后
的离线回退。OCR 端口均保持回环监听，不经过 VPS 反向代理。

从 VPS 完成 WireGuard 后先执行：

```bash
curl --fail --header 'Host: APP_DOMAIN' http://10.66.0.2:8000/api/v1/health
```

## 可选原生 WireGuard 与 TLS

以下内容仅适用于获得 A100 宿主机管理员权限后的原生 PostgreSQL/Redis/Celery
升级路径；当前用户级 SSH 隧道部署不执行这些步骤。

1. 在 VPS 和 A100 分别生成 WireGuard 私钥，使用 `deploy/vps/wireguard/*.example` 创建 `wg0`；私钥绝不进入 Git。
2. VPS 监听 `51820/udp`，A100 设置 `PersistentKeepalive = 25`。
3. 在 DNS 中创建 `A APP_DOMAIN -> VPS_PUBLIC_IP`，不创建 A100 API 子域名。
4. 构建前端 `npm --prefix frontend run build`。
5. 在 VPS 配置 `deploy/vps/.env` 后运行 `sudo deploy/vps/setup-caddy.sh`。

`deploy/vps/caddy/trip-helper.caddy`：

- 静态文件位于 `/var/www/trip-helper`，SPA 通过 `try_files` 回退到 `index.html`。
- `/api/` 转发到 `http://10.66.0.2:8000`。
- API 使用 `flush_interval -1`，上传字节不会持久化到 VPS。

防火墙：VPS 只允许受限 SSH、TCP `80/443`、UDP `51820`；A100 只允许受限 SSH 和 `wg0` 上的 TCP `8000`，禁止公网 `8000/5432/6379/8118`。

## 迁移、备份与上线

旧 SQLite 的 `folder_path` 是 Windows 本机路径，不能直接迁入新系统。迁移顺序：加密备份旧数据库和原件 -> 只读导入元数据到 PostgreSQL -> 丢弃或私有化旧路径 -> 通过新版上传或经批准的离线传输将原件写入 A100 storage -> 按项目核对文档数、已确认金额、汇总、异常和导出。

每天备份 A100 SQLite 数据库与文件卷到加密的异机位置；每月至少做一次隔离恢复演练。原生升级路径中同时备份 PostgreSQL；Redis 不是业务真相源。

上线前必须取得用户提供的 `APP_DOMAIN`、VPS SSH 别名、A100 存储路径、管理员邮箱和备份位置。当前仓库不会自动申请证书、修改 DNS 或传输真实数据。

## 自动化检查

```bash
PYTHONPATH=backend .venv/bin/python -m pytest tests backend/tests -q
.venv/bin/alembic -c backend/alembic.ini upgrade head
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```
