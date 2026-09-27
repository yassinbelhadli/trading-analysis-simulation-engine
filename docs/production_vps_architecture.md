# Production VPS Architecture

## Document Status

- Status: Design document — approved for writing, **not** an implementation or purchase authorization
- Scope: production VPS/cloud topology, process placement, network boundaries, capacity sizing
- Decision required from owner: which host split to buy (recommendation provided)
- Related docs: `docs/platform_architecture.md`, `docs/architecture.md`, `docs/infrastructure_activation_report.md`, `docs/backend_v2_freeze.md`
- This document changes **nothing**: no DNS records, no deployment, no code, no credentials.

## Executive Summary

**MT5/EA runtime must remain on a Windows host.** This is a hard constraint of the current codebase, not a preference.

Evidence:

- `core_engine/mt5_runtime.py:8` executes `import MetaTrader5 as mt5` at module load.
- The `MetaTrader5` Python package only runs on Windows and requires the MetaTrader 5 terminal installed on the same machine.
- `core_engine/mt5_runtime.py:72` hardcodes `C:\Program Files\MetaTrader 5\terminal64.exe`.
- `core_engine/engine_runner.py:19` imports `MT5Runtime` at the top of the module, so the engine runner cannot even import without `MetaTrader5` installed.
- `core_engine/execution/execution_engine.py:14` has the same top-level dependency.
- The user-facing EA (`storage/ea/ict_ea_v1.2.0.ex5`) runs inside the MetaTrader 5 terminal, which is Windows software.

The current code cannot be made Linux-only. Options are:

1. **Hybrid split (recommended):** Linux control-plane VPS + separate Windows trading-host VPS.
2. **Single Windows VPS:** everything on one Windows Server. Works but costs more and adds operational friction (PostgreSQL, Redis, Docker, Node on Windows).
3. **Linux + MT5 under Wine:** not production-grade for funded accounts. Rejected.
4. **Future MT5 bridge (like the existing MT4 bridge):** would eventually allow a thin Windows terminal host with the engine worker on Linux. Requires a separately approved engine-boundary phase. The current `mt5_bridge/Experts/ICT_Funded_EA.mq5` and `mt5_bridge/Include/*.mqh` are empty stubs; the MT5 bridge does not exist yet.

## Target Topology (Recommended)

```text
Public Internet
      |
      v
+--------------------------------------------------+
|  Linux Control-Plane VPS                          |
|  Cloudflare/WAF + Nginx :443                     |
|      +--> www.ictfundedeapro.com   (Website)     |
|      +--> app.ictfundedeapro.com   (Client)      |
|      +--> admin.ictfundedeapro.com (Admin)       |
|      +--> owner.ictfundedeapro.com (Future)      |
|      +--> api.ictfundedeapro.com   (FastAPI)     |
|      +--> hooks.ictfundedeapro.com (Future)      |
|                                                   |
|      PostgreSQL :5432 (private)                  |
|      Redis :6379 (future shared events/cache)    |
|      Telegram worker                             |
|      News worker                                 |
|      Render worker                               |
|      Scheduler worker (future)                   |
+----------------------+---------------------------+
                       |  private tunnel (WireGuard / provider private net)
                       |  PostgreSQL only, outbound from Windows host
+----------------------+---------------------------+
|  Windows Trading-Host VPS                         |
|                                                   |
|      MetaTrader 5 terminal(s) + EAs              |
|      MetaTrader 4 terminal + bridge EA           |
|      mt4_bridge :9100 (loopback)                 |
|      background_runner / engine worker           |
|      account scanner                             |
|      engine_manager state (process-local)        |
|      broker credentials (encrypted at rest)      |
+--------------------------------------------------+
```

## Why the Split Is Required

### Processes that hard-require Windows

Any process that imports `MetaTrader5` or `MT5Runtime` must run on a machine with the MetaTrader 5 terminal installed:

| Process | Windows requirement |
|---|---|
| `scripts/background_runner.py` | 24/7 engine worker; imports `MetaTrader5`; launched via `cmd /c start` on Windows |
| `core_engine/engine_runner.py` (`EngineRunner`) | Top-level `MT5Runtime` import |
| `core_engine/execution/execution_engine.py` (`ExecutionEngine`) | Top-level `MT5Runtime` import |
| `core_engine/mt5_runtime.py` (`MT5Runtime`) | `import MetaTrader5` + hardcoded terminal path |
| `core_engine/execution/mt5_adapter.py` (`MT5Adapter`) | Lazy `import MetaTrader5`; still needs terminal |
| MetaTrader 5 terminal + `ict_ea_v1.2.0.ex5` | Native Windows application |
| MetaTrader 4 terminal + bridge EA | Native Windows application |
| `mt4_bridge/main.py` | Best placed on Windows next to the MT4 terminal (loopback) |

### Processes that can run on Linux

| Process | Why it is Linux-viable today |
|---|---|
| FastAPI API (`api/main.py`) | Routes import `core_engine.engine_manager`, which has no `MetaTrader5`/`MT5Runtime` import |
| Next.js portals (`admin_dashboard/`) | No engine import |
| Website (`website/`) | No engine import |
| Telegram bot (`telegram_bot/bot.py`) | Uses lazy `create_mt_runtime` only in `mt_connector.py`; MT5 account checks would need Windows at runtime, but the bot process boots on Linux |
| News engine | No engine import |
| PostgreSQL, Redis | Native Linux services |
| Render worker | No engine import |

### MT4 is already remote-capable

`core_engine/mt4_runtime.py` talks to the MT4 bridge over HTTP (`http://localhost:9100` default, configurable `server`). The EA pushes data to the bridge. This means MT4 accounts already work across a network boundary.

Two caveats documented in `docs/architecture.md`:

- The MT4 bridge is currently **read-only** (no `/order/*` write endpoints), so `MT4Runtime.place_order` fails against the real bridge.
- MT5 has **no bridge at all** — only the in-process runtime. The MT5 bridge files are empty stubs.

A future MT5 bridge (mirroring the MT4 pattern) is the path to shrinking the Windows surface, but it touches the frozen engine boundary and requires a separate approved phase.

## Host Placement Summary

| Component | Linux control plane | Windows trading host |
|---|:---:|:---:|
| Nginx / TLS / WAF | x | |
| Website `www` | x | |
| Client portal `app` | x | |
| Admin portal `admin` | x | |
| Owner portal (future) | x | |
| FastAPI `api` | x | |
| PostgreSQL | x | |
| Redis (future) | x | |
| Telegram worker | x | |
| News worker | x | |
| Render worker | x | |
| Scheduler (future) | x | |
| MT4 bridge `:9100` | | x (loopback to terminal) |
| MT5 terminal + EA | | x |
| MT4 terminal + bridge EA | | x |
| Engine worker (`background_runner`) | | x |
| Account scanner | | x |
| Broker credentials | | x (encrypted; never on Linux) |

## Nginx Routing

Only `api`, `www`, `app`, `admin`, and future `owner`/`hooks` are public. Everything else stays private.

| Hostname | Upstream |
|---|---|
| `www.ictfundedeapro.com` | Website (Next.js) |
| `app.ictfundedeapro.com` | Client portal (Next.js) |
| `admin.ictfundedeapro.com` | Admin portal (Next.js) |
| `owner.ictfundedeapro.com` (future) | Owner portal (Next.js) |
| `api.ictfundedeapro.com` | FastAPI `:8000` |
| `hooks.ictfundedeapro.com` (future) | Webhook handler behind FastAPI |
| `downloads.ictfundedeapro.com` (future) | Signed object-storage redirect |

Rules:

- HTTPS only, HTTP 301 to canonical `https://` host. The current `ictfundedeapro.com -> http://www.ictfundedeapro.com/` redirect is manual and unchanged by this document.
- Rate limiting at edge and at Nginx.
- `app`, `admin`, `owner` must be separate origins with independent CORS settings pointing only at `api.ictfundedeapro.com`.
- No public route may proxy to the MT4 bridge, MT5 terminal, engine worker, PostgreSQL, or Redis.

## Network and Security Boundaries

- Broker credentials live **only** on the Windows trading host, encrypted at rest. They must never be sent to the Linux host.
- The Windows host connects **outbound** to PostgreSQL on the Linux host over the private tunnel. The Linux host never initiates into the Windows host.
- Private link options (owner decision): WireGuard tunnel, provider private network, or Tailscale. WireGuard is the baseline recommendation.
- MT5/MT4 WebRequest allow-lists on the terminals point only at the local bridge (`127.0.0.1:9100`) or the private API endpoint — never at public IPs.
- Firewall on the Linux host: public `:80/:443` only; PostgreSQL/Redis/workers on private interface.
- Firewall on the Windows host: private-tunnel access only; RDP restricted to an approved IP/zero-trust client; no public MT ports.
- Secrets are injected through a secret manager. No credentials in source, docs, or committed `.env`.
- All flows must remain fail-closed: news failure, spread failure, risk violation, runtime disconnect → no real trades, notify the client.

## Data Flow

### Client account connection

```text
Client browser -> app.ictfundedeapro.com
  -> api.ictfundedeapro.com/api/client/accounts
  -> ClientAccountService / LicenseService
  -> MTConnector (Windows host): MT5Runtime or MT4Runtime
  -> AccountRepository / ScanRepository -> PostgreSQL (Linux)
  -> engine control request after commit boundary
```

The browser never receives broker passwords.

### Trade execution

```text
Engine worker (Windows host)
  -> MT5 terminal or MT4 bridge
  -> market data
  -> detection / scoring / risk / news / spread guards
  -> execution or paper trading
  -> durable read model -> PostgreSQL (Linux host)
  -> durable events (future) -> Telegram/news workers (Linux host)
```

The engine worker writes state to PostgreSQL on the Linux host, so portals read the same source of truth. The API's in-process `engine_manager` is a process-local view; production engine status must come from the durable read model, not from the API singleton.

## Capacity Sizing (Estimates — decision, not purchase)

Sizes depend on the number of active funded accounts and symbols. Minimum viable estimates:

| Host | Minimum | Notes |
|---|---|---|
| Linux control plane | 2 vCPU, 4 GB RAM, 60 GB SSD | Nginx + API + PostgreSQL + Node portals + workers on one box is tight; 4 vCPU/8 GB is the comfortable tier |
| Windows trading host | 2 vCPU, 4 GB RAM, 40 GB SSD | Per MT5 terminal footprint; Windows Server licensing cost applies |

Scaling rule: never run the engine worker on the same machine as the control plane in production. Isolation protects capital protection if the API or Nginx is attacked or crashes.

## Option Comparison

| Option | Windows requirement | Cost | Operational friction | Verdict |
|---|---|---|---|---|
| Hybrid split (Linux + Windows VPS) | Only trading host | Medium (two hosts) | Low: standard stack on Linux, MT stack isolated on Windows | **Recommended** |
| Single Windows VPS | Everything | High (Windows Server + licensing) | PostgreSQL/Redis/Docker/Node on Windows are second-class; single point of failure | Acceptable only for early pilot with few accounts |
| Linux + MT5 under Wine | Circumvented | Low | Fragile, unsupported, risky for funded accounts | Rejected |
| Future MT5 bridge | Thin terminal host | Medium after engineering | Requires approved engine-boundary phase | Long-term path, not now |

## What This Document Does NOT Authorize

- No VPS purchase or provider selection.
- No DNS record changes (`app`, `api`, DKIM, DMARC, redirects remain manual and unapproved).
- No deployment, Docker files, Nginx configs, or compose files.
- No code changes, including to the frozen engine boundary.
- No MT5 bridge implementation or Wine setup.
- No SMTP/real-email tests (still blocked on mailbox credentials).

## Open Decisions Requiring Approval

1. Host split: hybrid (recommended) or single Windows VPS pilot?
2. Linux provider and tier; Windows provider and tier.
3. Private link: WireGuard vs provider private network vs Tailscale.
4. Windows host location/region relative to brokers (latency to broker servers matters).
5. Number of MT5 terminals per Windows host for the pilot.
6. RDP/zero-trust access policy for the Windows host.
7. Whether the MT4 bridge stays read-only (keep MT4 real execution off until a separate approval).
8. DNS subdomain plan (`app`, `api`, `admin`) — manual, after topology is fixed.

## Rollout Order (Gated)

1. Approve this topology and the host split. (owner)
2. Buy the VPSes. (owner)
3. Manually configure DNS subdomains after the Linux host is up. (owner, manual — not automated)
4. Deploy the control plane (API, portals, DB, workers) on Linux. (separate approved production phase)
5. Deploy the Windows trading host: terminals, EAs, bridge, engine worker, private tunnel. (separate approved phase)
6. Real SMTP + real broker E2E with non-production credentials. (blocked until mailbox credentials)
7. Manual client journey, monitoring, backups, rollback runbook. (production phase)

## Rollback Notes

- No rollback applies to this document because nothing was changed.
- If the topology decision changes before purchase, only this document is updated.
- If a purchased host becomes unnecessary, no code change is required; hosts can be decommissioned without data loss as long as PostgreSQL backups were exported first.
- The Windows trading host is never a storage authority: all durable state lives in PostgreSQL on the Linux host.

## Stop Condition

This document is complete. The next step is an explicit owner decision on the host split and provider selection. No DNS, deployment, code, or purchase action is taken from this document alone.
