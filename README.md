# Trip Helper

Trip Helper 是可从浏览器访问的差旅和日常票据整理 Web 应用。浏览器只通过一个 HTTPS 域名访问系统；A100 是唯一的数据和计算后端，保存原件、预览、OCR 原文、SQLite 数据和导出文件。

## 架构

```text
浏览器
  -> https://APP_DOMAIN
  -> VPS: Caddy + TLS + React 静态文件 + 反向代理
  -> VPS 回环 SSH 反向隧道
  -> A100: FastAPI + SQLite + MinerU OCR + 持久化文件存储
```

- VPS 不保存上传的票据，只对 `/api/` 请求进行无缓冲转发。
- A100 API、SQLite、原件、预览、OCR 原文和导出均位于 A100 用户目录；API 仅绑定 `127.0.0.1`。
- SSH 隧道仅在 VPS 的 `127.0.0.1:19829` 监听，A100 不开放公网 API 端口。
- 前端固定使用同源 `/api/v1`，不会直接连接 A100，也不会请求 `127.0.0.1` 的生产地址。
- 认证使用 Argon2 密码哈希、HttpOnly 会话 Cookie、SameSite=Lax 和 CSRF 请求头。所有项目、文件、任务、导出和设置都按用户所有权过滤。

## 本机浏览器验收

这一组命令使用 SQLite 和 eager 任务作为一次性浏览器验收环境，不需要 Docker、PostgreSQL、Redis 或 GPU。生产和完整本地开发仍使用原生 PostgreSQL、Redis 与独立 Celery 进程。

图片和扫描件的识别顺序为 A100 本地 PaddleOCR、可选的原生 MinerU、已配置的服务端远程视觉模型、原生 Tesseract 中文/英文兜底。Linux 本机验收需要 Tesseract 时安装 `tesseract-ocr` 和 `tesseract-ocr-chi-sim`；未安装时系统仍会保留可人工复核的票据，不会暴露远程密钥给浏览器。

准备依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --editable backend pytest
npm --prefix frontend ci
```

在三个终端分别执行：

```bash
scripts/run-local-web-api.sh
```

```bash
scripts/create-local-web-admin.sh --email admin@example.com
```

第二条命令会隐藏输入密码，密码至少 6 个字符。

```bash
VITE_DEV_API_TARGET=http://127.0.0.1:8001 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174
```

浏览器打开 `http://127.0.0.1:5174/login`，使用刚创建的管理员账号登录，然后创建项目、上传 PDF/JPG/PNG、等待任务完成、人工复核并生成导出文件。运行时数据位于被忽略的 `.local-web-runtime/`。

## 原生完整本地栈

需要验证 PostgreSQL、Redis、Celery 队列或 GPU OCR 时，安装本机 PostgreSQL 和 Redis 服务后使用：

```bash
cp deploy/local/.env.local.example deploy/local/.env.local
deploy/local/start.sh bootstrap
deploy/local/start.sh api
```

在其他终端启动 CPU worker、GPU worker（有 NVIDIA 驱动时）和 Vite：

```bash
deploy/local/start.sh worker-cpu
deploy/local/start.sh worker-gpu
deploy/local/start.sh frontend
```

详见 [deploy/local/README.md](deploy/local/README.md)。

## 测试与构建

```bash
PYTHONPATH=backend .venv/bin/python -m pytest tests backend/tests -q
.venv/bin/alembic -c backend/alembic.ini upgrade head
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

端到端浏览器检查：

```bash
npx --prefix frontend playwright install chromium
npm --prefix frontend run test:e2e
```

## A100 与 VPS 部署

当前部署使用 A100 用户级 SSH 隧道，不要求 A100 sudo。实际域名、会话密钥、管理员密码和存储内容均不写入仓库。

- A100 隧道服务与可选原生 systemd 单元：[deploy/a100/README.md](deploy/a100/README.md)
- VPS 静态发布、Caddy、TLS 和 SSH 隧道上游：[deploy/vps/README.md](deploy/vps/README.md)
- 架构与验收基线：[docs/a100-vps-refactor-deployment.md](docs/a100-vps-refactor-deployment.md)

不要使用旧的 Windows `start.bat`、服务端选文件夹、`folder_path` 扫描或旧 `/api/*` 接口来启动 Web 版本。这些文件仅保留为旧本地版本的回归参考。
