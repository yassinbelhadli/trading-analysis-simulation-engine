# Production Windows VPS Specification

## Document Status

- Status: Design/specification document — approved for writing, **not** a purchase, configuration, or deployment authorization
- Target: run the complete platform on **one Windows VPS**
- Decision: single-host Windows production pilot
- Related: `docs/production_vps_architecture.md`, `docs/platform_architecture.md`, `docs/infrastructure_activation_report.md`, `docs/backend_v2_freeze.md`
- This document changes **nothing**: no code, no DNS, no environment, no purchase.

## Reading Guide

- **Measured fact (MF):** verified directly from this repository or its local installs.
- **Estimate (EST):** extrapolated from measured footprints plus industry-standard runtime behavior; must be validated with a monitored pilot.

---

## 0. Decision Summary

| Tier | vCPU | RAM | NVMe SSD | Transfer | Windows | Concurrent MT5 terminals |
|---|---|---|---|---|---|---|
| **Minimum** | 4 | 8 GB | 160 GB | 3-4 TB/mo | Server 2022 Std (Desktop) | 1 |
| **Recommended MVP** | 6 | 16 GB | 320 GB | 5-10 TB/mo | Server 2022 Std (Desktop) | 2-4 |
| **Growth: 5 MT5 accounts** | 8 | 24 GB | 500 GB | 8-12 TB/mo | Server 2022 Std (Desktop) | 4-5 |
| **Growth: 20 MT5 accounts** | 16 | 64 GB | 1 TB | 15-25 TB/mo | Server 2022 Std (Desktop) | 10-12 |
| **Growth: 50 MT5 accounts** | **Not recommended on one Windows VPS** — split to multiple Windows hosts or the Linux+Windows hybrid | | | | | 2 hosts x ~10-12 |

Single recommended choices:

- **Minimum:** 4 vCPU / 8 GB RAM / 160 GB NVMe — pilot only, one MT5 terminal, low margin for Chromium renders.
- **Recommended MVP:** 6 vCPU / 16 GB RAM / 320 GB NVMe — the target for production start.
- **Growth:** do not exceed **~12 concurrent MT5 terminals per Windows host**; at 20+ accounts plan the second host or the hybrid topology in `docs/production_vps_architecture.md`.

No provider is recommended in this document (see section 16).

---

## 1. Measured Platform Inventory

### 1.1 Python runtime (from `.venv`)

| Package | Version | Purpose | Notes |
|---|---|---|---|
| fastapi / uvicorn / starlette / pydantic | 0.139 / 0.51 / 1.3 / 2.13 | API | uvicorn dev flag currently `reload=True` (must be disabled in production) |
| asyncpg / psycopg2-binary / SQLAlchemy / alembic | 0.31 / 2.9 / 2.0.51 / 1.18 | PostgreSQL | async pool `pool_size=10, max_overflow=20` (up to 30 conns per process); 15 Alembic revisions exist |
| metatrader5 / pywin32 | 5.0.5735 / 312 | MT5 runtime | **Windows-only**; one active terminal connection per process |
| numpy / pandas / scipy / matplotlib / mplfinance | 2.5 / 3.0 / 1.18 / 3.11 / 0.12 | Detection/analytics | Heavy import time + RAM; loaded by API and engine |
| python-telegram-bot | 22.8 | Bot | Polling mode (outbound only) |
| playwright / pillow | 1.61 / 12.3 | Chart capture | Chromium is a runtime dependency of the engine render path |
| bcrypt / passlib / python-jose / cryptography / ecdsa | various | Auth/encryption | |
| httpx / requests / dnspython / email-validator | various | Outbound HTTP/SMTP | |

Disk (measured on the dev machine; production is leaner but representative):

| Area | Size |
|---|---:|
| `.venv` | 505 MB |
| `admin_dashboard/node_modules` + `.next` | 351 MB + 391 MB |
| `website/node_modules` + `.next` | 331 MB + 95 MB |
| Playwright browser cache | 688 MB (Chromium + headless shell + ffmpeg) |
| Source tree (excl. the above) | 74 MB |
| `data/` (news/processed CSV) | 52 MB |
| `storage/` (EA builds) | 3 MB |

### 1.2 Node runtime

| App | Framework | Production command |
|---|---|---|
| `admin_dashboard/` (Client + Admin portals) | Next.js 15, React 19 | `next start` |
| `website/` (public site) | Next.js 15.5, React 19 | `next start` |

Both apps build with `next build` (Node 20 is the environment used in dev; pin the same major for production).

### 1.3 PostgreSQL and Redis reality

- PostgreSQL is used by the API, engine, scanner, and Telegram bot through `async_session_factory` (SQLAlchemy async). Each process holds its own engine; the API alone can hold up to 30 connections (10 pool + 20 overflow).
- **No Redis usage exists in application code today.** No `redis` Python package is installed. Redis is planned only for a future shared cache/event/lock phase (`docs/platform_architecture.md`). The VPS spec keeps a slot for it but it is not required for launch.
- Current default `DATABASE_URL` is a local dev default with embedded dev credentials; production must override via environment variable.

### 1.4 Runtime processes (measured from code)

| Process | Entry point | Port | Where |
|---|---|---|---|
| FastAPI control plane | `python -m api.main` (uvicorn) | 8000 | Public via proxy only |
| Telegram bot | `python telegram_bot/bot.py` (polling) | none inbound | Private |
| Engine worker | `python -m scripts.background_runner` (detached via `scripts/launcher.vbs`) | none | Private |
| MT4 bridge | `python -m mt4_bridge.main` | 9100 | Localhost |
| MT5 terminal(s) + EA | `terminal64.exe` (Windows) | none inbound | Private GUI session |
| Admin/Client portal | `next start` (admin_dashboard) | 3000 | Private |
| Website | `next start` (website) | 3010 | Private |
| PostgreSQL | Windows service | 5432 | Localhost |
| Redis (future) | Windows service | 6379 | Localhost |

Startup behavior measured:

- The API startup starts a **NewsService** polling thread (ForexFactory → CSV, default 60 min) and a **news broadcast loop** (every 10 min). It also calls `init_db()` (`create_all`) — acceptable for dev; production should use the 15 Alembic revisions.
- The Telegram bot starts `AlertService` + `RenderService`; render is PIL-based, with Chromium (`tv_screenshot`) used by the engine render path for TradingView-style images.
- The engine worker (`background_runner`) writes `logs/heartbeat.json` (30 s) and `logs/health_report.json` (60 min) — existing self-monitoring primitives.

### 1.5 MT4/MT5 integration model (measured)

- **MT5:** in-process `MetaTrader5` package. `core_engine/mt5_runtime.py` calls the global `mt5.initialize()`; `core_engine/engine_runner.py` and `core_engine/execution/execution_engine.py` import `MT5Runtime` at module load. The package supports **one active terminal connection per Python process** (MF). All accounts are currently handled inside **one** engine process (`background_runner`), so the current architecture supports **1 concurrent MT5 terminal per engine process**.
- **MT4:** HTTP bridge pattern (`mt4_bridge/main.py` on 9100, EA pushes via `WebRequest`). The bridge currently exposes **read-only** endpoints; `MT4Runtime` write methods have no bridge implementation yet (`docs/architecture.md`).

### 1.6 Networking facts (measured)

- Telegram uses `run_polling()` → **outbound only**, no inbound port required.
- SMTP is outbound (587 STARTTLS / 465 SSL) to `mail.privateemail.com`.
- All web surfaces terminate on the reverse proxy; nothing else needs a public port.
- CORS is currently `allow_origins=["*"]` (dev default) and must be set to explicit production origins at deployment time (not a code change now).

---

## 2. Requirements Derivation

The platform must run concurrently: FastAPI, 2 Next.js apps, PostgreSQL, engine worker, Telegram bot, MT4 bridge, at least 1 MT5 terminal, optional Chromium renders, and (future) Redis.

**Measured component footprint basis:**

| Component | RAM (typical) | CPU | Source of figure |
|---|---:|---|---|
| Windows Server 2022 (Desktop) | 2.0-2.5 GB | 1 core baseline | EST |
| PostgreSQL (tuned) | 0.5-1.0 GB | <1 core | EST (pool of 30 max conns, low write volume at pilot) |
| FastAPI (1 process) | 0.4-0.6 GB | <1 core | EST (numpy/pandas import weight) |
| Telegram bot | 0.2-0.35 GB | <0.5 core | EST |
| Engine worker (`background_runner`) | 0.3-0.6 GB | 1 core during detect cycles (30 s interval) | EST |
| MetaTrader 5 terminal (1) | 0.4-0.8 GB idle, up to ~1.5 GB with charts | 1-1.5 cores | EST (industry-standard terminal footprint) |
| Next.js admin_dashboard | 0.2-0.4 GB | <0.5 core | EST |
| Next.js website | 0.15-0.3 GB | <0.5 core | EST |
| Chromium headless (transient) | 0.2-0.5 GB spike | brief spike | MF local cache 688 MB; per-capture spike EST |
| Redis (future) | 0.1-0.3 GB | <0.3 core | EST |

Sum for the pilot (1 MT5 terminal, no concurrent renders): **~4.2-6.3 GB**. Add 20-25% headroom → **8 GB is the honest minimum; 16 GB is the safe MVP.**

---

## 3. Minimum VPS Specification

- **CPU:** 4 vCPU
- **RAM:** 8 GB
- **Storage:** 160 GB NVMe SSD (measured footprint ~2.4 GB dev / ~1.5-2 GB production plus Windows Server ~30-40 GB, leaving room for PostgreSQL data, backups staging, and growth)
- **Bandwidth:** 3-4 TB/month outbound (light web traffic; chart images are small PNGs)
- **OS:** Windows Server 2022 Standard, Desktop Experience. **Server Core is not viable** because MetaTrader 5 requires an interactive desktop session for terminal + EA operation.
- **Verdict:** works for the pilot with exactly 1 MT5 terminal, low admin/client traffic, and rare chart renders. Thin margin; use only if budget forces it.

## 4. Recommended MVP Specification (the target)

- **CPU:** 6 vCPU
- **RAM:** 16 GB
- **Storage:** 320 GB NVMe SSD
- **Bandwidth:** 5-10 TB/month
- **OS:** Windows Server 2022 Standard, Desktop Experience; keep an RDP session alive (or autologon) so MT5 terminals stay in an active desktop session.
- **Verdict:** supports the full platform plus **2-4 concurrent MT5 terminals**, periodic Chromium renders, PostgreSQL + future Redis, and monitoring headroom. **This is the recommended purchase target.**

## 5. Growth Specification

Per-account incremental cost (EST, after the first terminal shares the platform):

- +1 MT5 terminal + 1 engine process ≈ **+2-3 GB RAM** and **+1.5-2 vCPU**.
- +Chromium render concurrency: keep headless Chromium captures serialized; each concurrent render needs +0.5 GB transient.

| Accounts | vCPU | RAM | Storage | Notes |
|---|---|---|---|---|
| 5 MT5 accounts | 8 | 24 GB | 500 GB | 1 Windows host, 4-5 engine processes |
| 20 MT5 accounts | 16 | 64 GB | 1 TB | **Practical ceiling for one Windows VPS**; requires the multi-process/portable-terminal topology |
| 50 MT5 accounts | — | — | — | **Do not** place on one Windows VPS. Use multiple Windows hosts (<=10-12 terminals each) or the Linux control plane + Windows trading host in `docs/production_vps_architecture.md`. |

## 6. Concurrent MT5 Terminal Limit

**Measured constraint:** one active MT5 terminal per engine process (global `mt5.initialize()`). The current single `background_runner` process runs all accounts, so only **one** terminal is concurrently active today.

**Implication (EST-based sizing, topology not engine rewrite):**

- To run N accounts concurrently you need N portable MetaTrader 5 installations + N engine worker processes (one per terminal/account), each with its own `DATABASE_URL` and heartbeat identity. This is a **deployment topology change**, not a trading-engine change.
- Safe concurrency per host ≈ **floor(RAM / 2.5 GB)** and **<= ~12 terminals** per Windows host before split.
  - 16 GB → 4-5 terminals
  - 24 GB → 8-10 terminals
  - 64 GB → 20-24 terminals (host ceiling ~12 recommended for fault isolation)

Each terminal must run in an active desktop/RDP session; a disconnected session can throttle MT5.

## 7. CPU/RAM-Heavy Components

Ranked by measured/estimated impact:

1. **MetaTrader 5 terminals** — highest RAM consumer at scale; moderate CPU during chart/tick processing.
2. **Chromium (Playwright) chart captures** — highest transient CPU/RAM spikes; keep serialized.
3. **Engine worker** — pandas/numpy detection cycles every 30 s; high one-time import cost at start.
4. **FastAPI process** — pandas/numpy/scipy import weight in RAM; low steady CPU.
5. **PostgreSQL** — moderate RAM; benefits from `shared_buffers` tuning (0.5-1 GB).
6. **Next.js portals** — moderate RAM, low CPU.

Watchlist: import-time RAM spike on engine/API restart, and Chromium captures during market opens.

## 8. PostgreSQL + Redis on the Same VPS

**Yes, initially.** PostgreSQL (~0.5-1 GB) and future Redis (~0.1-0.3 GB) coexist comfortably on 16 GB with no port or resource conflict (5432 vs 6379). Keep both **localhost-only** with `listen_addresses` bound to 127.0.0.1. Redis is **not yet used by application code**; install it only when the shared event/cache phase is approved.

## 9. Docker/Containers vs Native Windows Services

**Recommendation: native Windows services/processes, not containers.** Reasons grounded in the project:

- The `MetaTrader5` Python package and MT5 terminals require a native Windows interactive desktop; Windows containers do not support GUI sessions reliably.
- The MT4 bridge EA whitelists `http://127.0.0.1:9100` via WebRequest — colocated native processes are the simplest match.
- The project already launches processes natively (`.ps1`/`.bat`/`launcher.vbs`); supervision maps directly to **NSSM** (Never Sleep Service Manager) or Windows Task Scheduler.
- PostgreSQL and Redis install as native Windows services via official installers.

Supervision choice (recommended): **NSSM** for API, bot, engine (single-instance guard), MT4 bridge, and both Next.js apps; Windows Task Scheduler "At startup" as a fallback; existing heartbeat files (`logs/heartbeat.json`) as the liveness signal for the engine.

## 10. Service/Process Layout

| # | Service | Executable/command | Supervision | Startup order |
|---|---|---|---|---|
| 1 | PostgreSQL | native service | Windows service (auto) | 1 |
| 2 | Redis (future) | native service | Windows service (auto) | 1 |
| 3 | Reverse proxy (Nginx/Caddy on Windows or IIS) | service | NSSM/Windows | 2 |
| 4 | FastAPI | `.venv\Scripts\python.exe -m api.main` (`uvicorn` with `reload=False`, 1 worker) | NSSM | 2 |
| 5 | Admin/Client portal | `admin_dashboard` `next start -p 3000` | NSSM | 2 |
| 6 | Website | `website` `next start -p 3010` | NSSM | 2 |
| 7 | Telegram bot | `.venv\Scripts\python.exe telegram_bot\bot.py` | NSSM | 3 |
| 8 | MT4 bridge | `.venv\Scripts\python.exe -m mt4_bridge.main` (127.0.0.1:9100) | NSSM | 3 |
| 9 | Engine worker(s) | `python -m scripts.background_runner` (one per MT5 terminal at scale) | NSSM with single-instance guard via PID/heartbeat | 3 (after terminal) |
| 10 | MT5 terminal(s) + EA | `terminal64.exe` (portable copy per account) | watchdog relauncher | 3 |

Notes:

- Run FastAPI **single-process** (1 uvicorn worker). `engine_manager` is process-local; multiple API workers would each hold divergent in-memory engine state (`docs/architecture.md`).
- Keep `reload=True` off; it is a dev flag.
- The API must use the **Alembic** revisions at deployment rather than `create_all` (migrations exist: 15 revisions).

## 11. Public Ports

Only:

| Port | Purpose | Protocol |
|---|---|---|
| 80 | HTTP -> HTTPS redirect | TCP |
| 443 | HTTPS (API, portals, website) | TCP |
| 3389 | RDP for administration (restrict to admin IPs or a VPN/zero-trust client) | TCP |

Nothing else is public.

## 12. Localhost/Private Services

| Port | Service | Why private |
|---|---|---|
| 8000 | FastAPI | Edge proxy is the only ingress |
| 3000 | Admin/Client Next.js | Proxy only |
| 3010 | Website Next.js | Proxy only |
| 9100 | MT4 bridge | Broker data; never public |
| 5432 | PostgreSQL | Never public |
| 6379 | Redis (future) | Never public |
| — | MT5 terminal connections | Outbound only to broker servers |

Telegram (polling) and SMTP are outbound; no inbound rules needed.

## 13. Windows Firewall Requirements

- Inbound: allow **80, 443** (public) and **3389** (restricted source IPs). Block all other inbound.
- Do **not** open 8000, 3000, 3010, 9100, 5432, or 6379 to the internet.
- Optionally enable the Nginx/Caddy or IIS service binding to 80/443 only.
- Outbound: default allow, but restrict RDP-adjacent services and note that MT5 terminals connect outbound to broker servers (443/trading ports) — do not block.
- Apply firewall rules at both the Windows Firewall and the provider's network security group (belt and braces).

## 14. Backup Requirements

| Data | Method | Frequency | Destination |
|---|---|---|---|
| PostgreSQL | `pg_dump` full + daily; enable WAL archiving to local staging then off-host | Daily full, continuous WAL (if enabled) | Staged on `D:\backups`, copied off-host nightly |
| Schema baseline | Alembic revisions (15 exist) + `alembic stamp/upgrade` runbook | On deploy | Git/object storage |
| Application data (`data/`) | Robocopy mirror | Daily | Off-host |
| EA builds (`storage/ea`) | Robocopy mirror + keep the immutable release artifact in object storage | Daily + on release | Off-host |
| Configuration | `config/.env` and deployment env files (encrypted) | On change | Secret manager / encrypted archive |
| Logs | Rotating logs; archive weekly (engine.log rotates at 50 MB, 3 backups) | Weekly | Off-host |
| Playwright/Chromium cache | Do not back up; reinstall via `playwright install` | — | — |

Off-host destination must be a different machine/provider (not another disk on the same VPS).

## 15. Recovery Strategy

| Failure | Detection | Recovery | Fail-safe |
|---|---|---|---|
| Process crash (API/bot/bridge/Next) | NSSM auto-restart + health probes | NSSM restarts within seconds | API reconnects DB pool automatically |
| Windows restart | Boot task | Task Scheduler "At startup" / NSSM auto-start all services in the order in section 10 | Autologon + startup batch restores RDP desktop for MT5 |
| MT5 crash | Watchdog detects `terminal64.exe` missing / engine heartbeat stale (>120 s — existing check in `scripts/start_background.ps1`) | Relaunch terminal, re-attach EA; engine reconnects | **No trades while disconnected (fail-closed)** |
| API crash | NSSM + `/admin/system-health` probes | Restart; `engine_manager` state is process-local and rebuilt from DB | No trading decisions live in the API |
| Database failure | Connection errors / health endpoint | Restore from last `pg_dump` + WAL; verify with Alembic | **Engine must not place real trades when risk/audit writes fail (fail-closed)** |
| Telegram bot crash | NSSM | Restart; polling re-registers | Events buffered in DB, not lost |
| Full host loss | External uptime monitor on 443 | Provision from backups on a fresh host (documented runbook) | Backups off-host |

## 16. Monitoring Requirements

Use existing primitives plus a lightweight external probe:

- **Liveness:** external HTTPS checks on the public site and `/admin/system-health` (token-gated) via a third-party uptime service.
- **Process health:** NSSM status + Task Manager performance baselines; a scheduled PowerShell check that fails when a required process is down or when `logs/heartbeat.json` is older than ~120 s.
- **Engine health:** existing `logs/heartbeat.json` (30 s) and `logs/health_report.json` (60 min) already contain uptime, cycles, MT5-connect, memory, CPU, active/stale trades. Alert on stale heartbeat and on `mt5_connected=false`.
- **PostgreSQL:** `pg_stat_activity` connection count (pool max 30/process) and disk usage; alert before the data volume fills.
- **Metrics:** Windows Performance Monitor counters (CPU, RAM, disk, network) exported to the chosen observability sink during the production phase.
- **Logs:** rotate and archive as in section 14; never log credentials (existing rule).
- **Renders:** watch Chromium capture duration; alert on >N seconds or consecutive failures.

## 17. Migration Path to Linux + Windows Trading Host (without rewriting the engine)

Feasible today because of the measured import graph:

- The FastAPI control plane, `admin_dashboard`, and `website` do **not** import `MetaTrader5`. `core_engine/engine_manager.py` has no MT5 import. These can move to Linux unchanged.
- The engine (`core_engine/engine_runner.py`, `execution_engine.py`, `mt5_runtime.py`, `mt5_adapter.py`), the `background_runner` worker, the account scanner, MT5 terminals, and the MT4 bridge **must stay on Windows** — they hard-require `MetaTrader5`/the terminal.

Migration steps (future phase, no action now):

1. Run PostgreSQL, FastAPI, both Next.js apps, Telegram/news workers on a Linux VPS.
2. Keep the Windows host running terminals + engine processes + MT4 bridge, connecting to the Linux PostgreSQL over a private tunnel (WireGuard/private net) — broker credentials stay on Windows.
3. Point `DATABASE_URL`, CORS origins, and public URLs at the Linux host; no trading-engine code changes.
4. Test the split with staging first, then cut over.

## 18. Monthly Resource Estimates (no provider recommendation)

| Tier | RAM-hours | vCPU-hours | Storage growth/mo | Transfer |
|---|---|---|---|---|
| Minimum (4c/8GB) | ~5,760 | ~2,880 | 5-10 GB (logs + DB + news CSV) | 3-4 TB |
| Recommended MVP (6c/16GB) | ~11,520 | ~4,320 | 10-20 GB | 5-10 TB |
| Growth 5 accounts (8c/24GB) | ~17,280 | ~5,760 | 20-40 GB | 8-12 TB |
| Growth 20 accounts (16c/64GB) | ~46,080 | ~11,520 | 50-100 GB | 15-25 TB |

These are estimates to compare offers, not a provider recommendation. Provider choice is a separate decision based on region (latency to broker servers), licensing (Windows Server), bandwidth pricing, and off-host backup options.

## 19. Production Hardening Notes (documented, not performed)

Measured dev defaults that must change **at deployment time** (no code change authorized in this phase):

- `uvicorn ... reload=True` → `reload=False`, 1 worker.
- `allow_origins=["*"]` → explicit production origins.
- `init_db()` `create_all` → Alembic `upgrade head` (15 revisions exist).
- Local dev `DATABASE_URL` → production credentials via environment/secret manager.
- `ADMIN_TOKEN`, `JWT_SECRET`, `ENCRYPTION_KEY` → strong production values via env.

## 20. What This Document Does NOT Authorize

- No VPS purchase, provider selection, or subscription.
- No code changes (including the trading engine).
- No DNS changes (`www`/`app`/`admin`/`owner`/`api`/`hooks`/`downloads`, DKIM, DMARC, redirects remain manual and unapproved).
- No deployment, firewall edits, service installs, or environment changes.
- No SMTP/real-email tests (still blocked on mailbox credentials).
- No Redis installation (not used by code yet).
- No Docker setup.

## 21. Rollout Order (Gated)

1. Owner approves one tier from section 0. (decision)
2. Owner selects provider/region; buys the VPS. (owner, manual)
3. Windows Server 2022 Desktop install + RDP hardening + firewall baseline. (manual)
4. Install PostgreSQL (+ Redis only when approved), Python venv, Node, Playwright browsers, and the two Next.js apps. (separate approved production phase)
5. Deploy API, bot, engine worker, MT4 bridge, MT5 terminal(s) with the section 10 supervision layout. (separate approved phase)
6. Configure DNS subdomains and HTTPS proxy **after** the host is up. (owner, manual — not automated)
7. Real SMTP + real broker E2E with non-production credentials. (blocked until mailbox credentials)
8. Monitoring, backups, recovery runbook, manual client journey. (production phase)

## 22. Rollback Notes

- This document performs no changes, so no rollback applies to it.
- If the chosen tier proves insufficient, scale the plan vertically first (RAM/CPU) before splitting hosts.
- If a purchased host is decommissioned, no code change is required; restore from the off-host PostgreSQL/`data`/`storage` backups on the next host.
- All durable state lives in PostgreSQL (`docs/platform_architecture.md`); the Windows host is never a storage authority.

## 23. Stop Condition

Specification complete. The next step is an explicit owner decision on the tier from section 0 and provider/region. No purchase, DNS, deployment, or code action is taken from this document alone.
