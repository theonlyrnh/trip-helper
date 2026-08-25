# Trip Helper Frontend

React/Vite single-page application served from the VPS under the same HTTPS domain as the API. Production API calls always use relative `/api/v1` URLs; browsers never connect directly to the A100 host.

## Development

```bash
npm ci
npm run dev
```

`vite.config.ts` proxies `/api/*` to `VITE_DEV_API_TARGET` during development. The default target is the local FastAPI listener. Do not define a production API base URL in frontend environment files.

## Checks

```bash
npm run lint
npm run build
npm run test
npx playwright install chromium
npm run test:e2e
```

Build output is `dist/`. The VPS Nginx configuration serves it with an SPA fallback and proxies `/api/` through WireGuard to the A100 API.
