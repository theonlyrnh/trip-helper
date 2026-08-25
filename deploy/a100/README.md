# A100 Runtime

The user-level acceptance fixture follows the existing Paper Wiki model: the
A100 user account runs FastAPI, SQLite, MinerU, and persistent file storage on
loopback. An SSH reverse tunnel makes that loopback API available to Caddy on
the VPS. Production uses the native PostgreSQL/Redis/systemd path below.

## User-Level Acceptance Tunnel

Run this from the A100 checkout as the regular application user:

```bash
deploy/a100/tunnel.sh bootstrap
deploy/a100/tunnel.sh setup
deploy/a100/tunnel.sh start
deploy/a100/tunnel.sh create-admin --email ADMIN_EMAIL
deploy/a100/tunnel.sh create-user --username USERNAME
deploy/a100/tunnel.sh test
```

`tunnel.sh` creates an ignored `deploy/a100/.env.tunnel` with a random session
secret and bootstrap token, keeps SQLite and uploads in
`~/.local/share/trip-helper`, starts FastAPI on `127.0.0.1:18001`, and maintains
the SSH reverse tunnel `VPS 127.0.0.1:19829 -> A100 127.0.0.1:18001`.

Use `status`, `restart`, and `stop` for lifecycle management. The script owns
only its PID files and never terminates an unrelated process.

This path is explicitly local-acceptance-only: it keeps SQLite, an in-memory
Celery broker, and eager execution because no user-level Redis service is
assumed. Do not use it as the production worker topology. Production uses the
native setup below, with PostgreSQL, Redis, and separate CPU/GPU workers.

The target A100 already has native MinerU 3.3.1 at `127.0.0.1:8888`. Its health
endpoint has been verified. Keep it loopback-only and point the application at
its multipart endpoint:

```dotenv
OCR_PROVIDER=mineru
MINERU_API_URL=http://127.0.0.1:8888
MINERU_ENABLED=true
MINERU_BACKEND=hybrid-engine
MINERU_PARSE_METHOD=auto
```

Verify it before enabling the worker:

```bash
curl --fail http://127.0.0.1:8888/health
curl --fail -F 'files=@SAMPLE_IMAGE' http://127.0.0.1:8888/file_parse
```

MinerU is managed separately from Trip Helper. The tunnel runtime consumes its
loopback API and leaves its process owner and lifecycle unchanged.

`MINERU_API_URL` is optional. When it is absent, the API keeps the configured
PaddleOCR endpoint first and uses native Tesseract (`chi_sim+eng`) as the local
fallback. Do not expose port `8888` or `8118` outside the A100 loopback.

## Optional Native Service Deployment

`setup-a100.sh` and `systemd/` remain available for a future A100 host with
administrator access. That mode uses PostgreSQL, Redis, Celery workers, and
WireGuard `10.66.0.2:8000`; it is not the active no-sudo deployment path.
