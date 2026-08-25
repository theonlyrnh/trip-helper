# Local Native Runtime

This layout mirrors the production process split without containers.
PostgreSQL and Redis must run locally and bind to loopback before starting the
application processes.

```bash
cp deploy/local/.env.local.example deploy/local/.env.local
sudo systemctl enable --now postgresql redis-server
deploy/local/init-postgres.sh
deploy/local/start.sh bootstrap
deploy/local/start.sh api
deploy/local/start.sh worker-cpu
deploy/local/start.sh frontend
```

Run `deploy/local/start.sh check` to verify PostgreSQL and Redis. Start the GPU
worker only on a host where `nvidia-smi` succeeds:

```bash
deploy/local/start.sh worker-gpu
```

PaddleOCR remains the first image OCR provider. When a loopback MinerU service
is detected on an A100 it can be selected automatically or via
`OCR_PROVIDER=mineru`; the local template also enables native `tesseract` with
`chi_sim+eng` as the final fallback.

The native development frontend continues to use Vite. Production frontend
assets are served by the VPS Caddy configuration in `../vps/caddy/`.
