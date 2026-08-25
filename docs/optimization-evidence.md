# Full Optimization Execution Evidence

This log is intentionally limited to reproducible local evidence. Runtime data,
credentials, backups, and generated build directories are excluded from Git.

## Stage 0 baseline (2026-08-25)

```text
branch: main
head: 04a4bc25225e228567c544e2dd81a33d4ca8b45e
archive: backups/trip-helper-baseline-20260825-233812/worktree.tar.gz
archive checksum: OK (sha256sum -c backups/trip-helper-baseline-20260825-233812/worktree.tar.gz.sha256)
```

The worktree contained pre-existing user edits before this execution. They are
preserved; no reset, clean, checkout, force push, or destructive database
operation is used.

## F-ID mapping

| ID | Reproduction/closing test | Implementation boundary | Acceptance command |
| --- | --- | --- | --- |
| F-01 | `test_date_range_contract_rejects_reverse_ranges` | `app/schemas.py`, `app/services/trips.py`, `app/domain/reporting/summary.py` | `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_optimization_contracts.py -q` |
| F-02 | `test_settings_drive_endpoint_count` plus API settings workflow | `app/services/trips.py`, `app/domain/reporting/summary.py` | same focused pytest command |
| F-03 | `test_summary_never_emits_negative_days_or_amounts_and_preserves_zero_allowance` | `app/domain/reporting/summary.py`, `app/services/trips.py` | same focused pytest command |
| F-04 | `test_empty_ocr_creates_manual_review_projection` plus OCR retry tests | `app/services/recognition.py`, `app/workers/tasks.py` | same focused pytest command |
| F-05 | `test_projection_rebuild_is_idempotent` | `app/services/trips.py`, database uniqueness | same focused pytest command |
| F-06 | `test_manual_dates_override_inference_and_conflicts_are_explained` | `app/services/trips.py`, `app/services/recognition.py` | same focused pytest command |
| F-07 | `test_worker_registry_is_loaded_by_standalone_entrypoint` plus worker startup smoke | `app/workers/celery_app.py`, `app/infrastructure/queue/celery.py` | focused pytest + worker smoke |
| F-08 | OCR retry/terminal-state tests and export failure path | `app/services/jobs.py`, `app/workers/tasks.py`, `app/services/exports.py` | focused pytest |
| F-09 | cancellation/conditional terminal transition tests | `app/services/jobs.py`, worker conditional transitions | focused pytest |
| F-10 | `test_stale_invoice_writer_is_rejected` | `app/services/invoices.py`, `Invoice.version` | focused pytest |
| F-11 | `test_sqlite_foreign_keys_are_enabled` | `app/infrastructure/db/session.py`, Alembic | focused pytest + Alembic upgrade |
| F-12 | clean wheel entry/package import smoke | `backend/pyproject.toml`, package imports | wheel build/install smoke test |
| F-13 | model constraint/index inspection and migration round trip | `backend/alembic/versions/` and models | Alembic upgrade/inspect |
| F-14 | `test_export_formats_escape_formulas_and_include_chinese_details` | `app/services/exports.py` | focused pytest |
| F-15 | `test_export_formats_escape_formulas_and_include_chinese_details` | `app/services/exports.py` | focused pytest |
| F-16 | same export test plus cleanup task | `app/services/exports.py`, cleanup task | focused pytest |
| F-17 | `test_private_streams_and_exports_set_no_store_headers` | document/preview/OCR/export endpoints | focused API pytest |
| F-18 | upload and bounded-file tests | storage/document/OCR adapters | focused pytest |
| F-19 | ownership/path tests in API workflow | deps/storage/upload API | focused pytest |
| F-20 | `test_documents_are_paginated_with_total_count` plus 1000-row query probe | `app/api/v1/documents.py`, `app/services/documents.py` | focused pytest + benchmark |
| F-21 | `test_tunnel_deployment_contract_is_explicitly_acceptance_only` plus CPU/GPU worker startup smoke | `deploy/*`, Celery config | shell smoke + focused pytest |
| F-22 | `test_health_readiness_and_session_lifecycle`, `test_login_limiter_uses_shared_counter_and_bounded_fallback` | `app/api/v1/auth.py`, `app/core/rate_limit.py` | focused pytest |
| F-23 | `test_health_readiness_and_session_lifecycle` and request correlation middleware | `app/api/v1/health.py`, `app/main.py`, logging | focused pytest |
| F-24 | `documentsApi.list` pagination/cancellation test and adaptive polling implementation | `frontend/src/app/query.ts`, workspace/API features | `npm --prefix frontend run test` |
| F-25 | frontend accessibility/responsive tests and screenshots | existing `frontend/src/index.css` and features | lint/typecheck/build/E2E |
| F-26 | layered production-similar smoke matrix | deploy scripts, tests, docs | full gate commands in final report |

## Baseline measurements

The current baseline gates before implementation were:

| Check | Result |
| --- | --- |
| Backend pytest (`tests backend/tests`) | 43 passed |
| Frontend lint | passed |
| Frontend typecheck | passed |
| Frontend unit tests | 29 passed |
| Frontend build | passed; 400.07 kB JS / 87.11 kB CSS |
| Alembic upgrade | passed against local SQLite |
| compileall | passed |
| safety scan | blocked by ignored fixture/vendor files and benign secret-shaped variable names; remediation is tracked in F-26 |

Later stage entries append commands, key output, measurements, checkpoint
identifiers, and residual risks below this section.

## Stage checklist

- [x] Stage 0: baseline and contracts; archive checksum and F-ID matrix recorded
- [x] Stage 1: installability, worker registration, and schema foundations
- [x] Stage 2: domain correctness
- [x] Stage 3: job lifecycle and queues
- [x] Stage 4: transactions, concurrency, and authorization
- [x] Stage 5: files, OCR, previews, and exports
- [x] Stage 6: query/resource performance
- [x] Stage 7: authentication, health, and observability
- [x] Stage 8: frontend workspace polish
- [x] Stage 9: release, backup, and rollback rehearsal; external production services remain blocked as documented below

## Stage evidence (2026-08-26)

### Local checkpoints

```text
33950fa checkpoint(opt): backend-contracts
7e7e7e7 checkpoint(opt): release-readiness
5570628 checkpoint(opt): workspace-polish
```

These are local commits only. The original baseline archive remains outside
Git, and unrelated root-level user edits remain untouched in the worktree.

### Stage 1: packaging, migrations, and workers

```text
.venv/bin/python -m pip wheel --no-deps --wheel-dir /tmp/... ./backend
required package entries: OK
clean wheel install with dependencies: clean wheel imports: OK
```

The wheel includes `app`, legacy `models`, `parsers`, `providers`, `services`,
`routers`, `exporters`, `utils`, and the legacy top-level modules needed by
those imports. A `timeout 6s` standalone Celery worker smoke was run for both
`cpu,default` and `gpu`; each process reached worker startup and listed
`execute_job`, `process_document`, and `recognize_document` before the
intentional timeout. Alembic `upgrade head -> downgrade 20260720_0001 ->
upgrade head` passed on an isolated SQLite database.

### Stage 2-5: correctness, lifecycle, and file safety

`PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q` passed **49**
tests. The focused contracts cover reverse dates, endpoint allowance rules,
zero/default amounts, settings snapshots, date conflicts, empty OCR manual
review, idempotent projections, conditional cancellation/terminal updates,
atomic invoice versions, SQLite foreign keys, formula escaping, Chinese PDF
details/font fallback, expiry cleanup, private response headers, and
ownership. OCR retry tests cover eager terminal failure and non-eager GPU
retry scheduling.

### Stage 6: pagination and performance

On Python 3.14 / SQLite with a fixed 1,000-document fixture and 30 requests:

```text
document list page=100: p50=8.63ms, p95=10.45ms, 7 SQL statements/request
summary with 1,000 documents: p50=2.63ms, p95=3.06ms, 4 SQL statements/request
```

The document API returns `X-Total-Count`, stable page metadata, and a bounded
page size. The browser loads pages until the short page and passes TanStack
Query cancellation signals.

### Stage 7: authentication, health, and observability

Readiness checks database, storage, queue, and OCR configuration; liveness is
separate. Login limiting uses a Redis atomic counter when configured and a
bounded local fallback during a Redis outage. Session listing, password change,
and revoke-all behavior are covered by API tests. Every request carries an
`X-Request-ID` correlation header and structured request completion logs.

### Stage 8: frontend

```text
npm --prefix frontend run lint       passed
npm --prefix frontend run typecheck  passed
npm --prefix frontend run test       30 passed
npm --prefix frontend run build     passed (400.62 kB JS, 87.11 kB CSS)
npm --prefix frontend run test:e2e  1 passed (Chromium workflow)
```

Polling pauses when the document is hidden, backs off after failures, and
passes abort signals through query functions. Existing colors, layout density,
navigation, and component structure remain unchanged.

### Stage 9: release, external probes, and rollback

```text
python /home/xr/.agents/skills/standardized-ai-development/scripts/ai_dev_safety_check.py .
OK: no blocking safety issues detected by this checker (0 findings)
git diff --check
passed
```

Available external probes on this host:

```text
nvidia-smi: NVIDIA A100 80GB PCIe
MinerU http://127.0.0.1:8888/health: healthy, version 3.3.1
pg_isready: unavailable (PostgreSQL service not installed/running)
redis-cli ping: unavailable (Redis service not installed/running)
docker info: permission denied on /var/run/docker.sock
```

The native production systemd units are configured for independent PostgreSQL,
Redis, CPU, and GPU services, but their cross-process execution cannot be
claimed on this host without Redis/PostgreSQL. The user-level SSH tunnel is
explicitly `TUNNEL_ACCEPTANCE_ONLY=true` and eager; it is not the production
worker topology. Local SQLite, eager contracts, worker registration, and GPU
presence provide the replacement evidence.

Rollback rehearsal used the isolated Alembic database: `upgrade head`,
`downgrade 20260720_0001`, and `upgrade head` all passed. Application rollback
is the preceding local checkpoint; schema rollback is the matching Alembic
downgrade or a verified database/file-volume backup. No production data or
credentials were touched.

## Rollback

Application rollback is to the preceding local checkpoint. Database changes
must use the matching Alembic downgrade or restore a verified database/file
backup; code rollback alone is not a schema rollback.
