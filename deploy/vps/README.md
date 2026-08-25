# VPS Native Runtime

The VPS is limited to public TLS, static React assets, and reverse proxying to
an A100 SSH reverse-tunnel endpoint. It has no application database, OCR
runtime, or uploaded file storage.

The active deployment target uses the existing Caddy instance. This preserves
other VPS sites while Caddy obtains and renews TLS for `APP_DOMAIN`.

1. Copy `.env.example` to `.env`, set `APP_DOMAIN`, and set `FRONTEND_DIST` to
   the built frontend directory on the VPS checkout.
2. Set `API_UPSTREAM=127.0.0.1:19829` in `.env`. This is the A100 user's SSH
   reverse-tunnel endpoint on the VPS.
3. Build the frontend and run `sudo deploy/vps/setup-caddy.sh`.
4. Confirm `caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile --validate`,
   `https://APP_DOMAIN`, and that the API is only reachable through Caddy.

`caddy/trip-helper.caddy` streams API traffic to `API_UPSTREAM` with
`flush_interval -1`; upload bytes are proxied to the A100 without storage on
the VPS. The A100 endpoint remains VPS-loopback only because the SSH tunnel
uses `-R 127.0.0.1:19829:127.0.0.1:18001`.
