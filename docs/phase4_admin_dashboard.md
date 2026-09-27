# Phase 4 — Admin Portal V2: Implementation Specification (PLANNING ONLY)

Status: **DRAFT — awaiting explicit approval. No code is written.**

---

## 1. Objective

Build the **Admin Portal V2** as an independent frontend application living in `admin_dashboard/`,
targeted at `https://admin.ictfundedeapro.com`. It is an operations control center for the business
team, fully separated from the Client Portal (`client_dashboard/`) and the marketing Website (`website/`).

Phase 4 is **frontend work only**, reusing the frozen Backend V2 contracts. Where a contract is
insufficient, this spec documents the exact gap and STOPS instead of implementing a workaround.

Minimum surfaces to define: Overview, Clients, Client Details, Licenses, MT5 Accounts, Trades,
Performance, Subscriptions, EA Builds/Downloads, Telegram, Support, Notifications, System Health,
Audit Logs, Security, Settings. (All 16 are covered in Section 4.2.)

---

## 2. Scope & Constraints

### 2.1 Hard limits (unchanged from plan)
- **Do NOT** modify the frozen Backend V2 (no route edits, no new endpoints, no new services/repositories/DTOs/aggregators).
  Only an explicitly approved contract bug may touch the backend.
- **Do NOT** deploy, configure DNS, or provision the VPS.
- **Do NOT** start Telegram or Billing implementations.
- **Do NOT** modify the Trading Engine.
- **Do NOT** modify the Client Portal (unless a critical defect is found and approved).
- **Do NOT** redesign Website W1.
- **Do NOT** implement or seed the future `developer` role.
- **Do NOT** create any speculative endpoint. Unused frozen endpoints may be *wired*; nothing new is invented.
- Workspace is **not a git repo** → any destructive frontend change must be preceded by a full backup
  of `admin_dashboard/` (see Section 11).

### 2.2 Reuse rules
- Reuse the frozen `GET /api/admin/*` contracts. No duplicate business logic in the frontend.
- Reuse existing components/patterns already proven in `client_dashboard/` (DataTable, ConfirmDialog, Toast, Skeleton, EmptyState, StatusBadge).
- Reuse the existing golden master QA for `/api/admin/overview`; do not re-test what is already frozen.

---

## 3. Current-State Inspection (verified)

### 3.1 Frontend (`admin_dashboard/`)
- Next.js 15 / React 19 / Tailwind 4, package name `admin-dashboard`.
- **Admin tree today:** `/dashboard/**` (Sidebar + Topbar) plus legacy standalone pages `/users`,
  `/licenses`, `/health`, `/audit`, `/accounts`, `/accounts/[id]`.
- **Client pages share this app:** everything under `app/client/**` (superseded by `client_dashboard/` in Phase 3).
- Shared auth in `lib/auth` (JWT + admin 2FA step); `lib/permissions.ts` currently gates only
  `owner` / `admin` (coarse); `lib/api.ts` exposes JWT `authFetch` **plus broken legacy aliases**
  (`listAccounts` → `/admin/accounts*`, `getRecentAudit` → `/admin/audit?limit=...`).
- `components/Sidebar.tsx` is dead code.

### 3.2 Backend admin contracts (frozen, authoritative)
- JWT-admin bundle: `api/routes/admin/bundle.py` → 13 sub-routers (overview, users, licenses, news,
  promotions, trading, roles, billing, clients, audit, system_health, tickets, settings), mounted at
  `/api` → effective prefix **`/api/admin/...`**, gated by `require_permission`.
- Legacy static-token routers mounted at `/admin` with `X-Admin-Token`
  (`verify_admin_legacy`, server-side `ADMIN_TOKEN`): `admin_health`, `admin_users`, `admin_accounts`,
  `admin_licenses`, `admin_audit`, `admin_metrics`. **These are NOT JWT-gated.**
- **Verified defect:** the current `/accounts` pages and the recent-audit widget call legacy
  `/admin/*` routes through JWT `authFetch` → they receive `401` because those routes require
  `X-Admin-Token`. `getRecentAudit` also targets `/admin/audit?limit=...`, which matches no legacy route.
  The MT5 Accounts surface therefore has **no working JWT source today**.

### 3.3 RBAC source of truth
- `security/access_control.py`: full `Permission` enum (Section 5.2), `ROLE_PERMISSIONS` (seed + fallback),
  `ROLE_HIERARCHY`, `has_permission` (DB-first, wildcard for `owner`).
- `security/auth.py`: `get_current_user`, `require_permission`, `has_permission`.
- `security/audit.py`: `log_event` (severity levels) + `AuditLog` model — audit is server-side.
- Services to reuse (read-only consumers, not modified): `api/services/admin_dashboard_query_service.py`,
  `api/services/admin_dashboard_aggregator.py`, `license_system/license_manager.py`.

### 3.4 Existing QA / docs
- Golden master: `scripts/_qa_backend_v2_admin_dashboard_golden.py` → `GET /api/admin/overview`.
- `docs/backend_v2_freeze.md`, `docs/architecture.md`, `docs/platform_architecture.md`,
  `docs/production_windows_vps_specification.md` (both portals on subdomains).
- Known pre-existing test debt (unrelated, do not block Phase 4): `test_all.py` stale `EVENT_EMOJI`
  import; `tests/test_permissions.py` 6/7 stale expected list.

---

## 4. Target Architecture

### 4.1 App boundaries
| App | Path | Purpose | Domain |
|---|---|---|---|
| Client Portal | `client_dashboard/` | client self-service | client.ictfundedeapro.com |
| **Admin Portal V2** | **`admin_dashboard/`** | **operations control center (this phase)** | **admin.ictfundedeapro.com** |
| Website | `website/` | marketing | www.ictfundedeapro.com |
| Owner Portal (future) | `owner/` (new, later) | control plane | owner.ictfundedeapro.com |

`admin_dashboard/` is repurposed in-place (it already hosts the admin pages). After Phase 4 it contains
**admin-only** routes; the old client pages inside it are removed (they exist in `client_dashboard/`).

### 4.2 Route tree (24 admin pages incl. the 16 required surfaces)

Permission shown is the minimum gate; backend `require_permission` remains the enforcement point.

```
/dashboard/*   (all behind AdminAuthGuard; per-page RequirePermission)
├── /dashboard                        Overview           [admin.overview]
├── /dashboard/clients                Clients            [clients.read]
│   └── /dashboard/clients/[clientId] Client Details      [clients.read + per-action]
├── /dashboard/licenses               Licenses           [licenses.read]
├── /dashboard/accounts               MT5 Accounts       [accounts.read]    (CONTRACT GAP §13.1)
│   └── /dashboard/accounts/[accountId]
├── /dashboard/trading                Trading Overview   [trades.read + admin.overview]
│   ├── /dashboard/trading/trades     Active Trades      [trades.read]
│   ├── /dashboard/trading/history    History            [trades.read]
│   ├── /dashboard/trading/signals    Signals            [trades.view]
│   ├── /dashboard/trading/risk       Risk Monitor       [trades.read]
│   ├── /dashboard/trading/performance Performance       [analytics.read]
│   ├── /dashboard/trading/engine     Engine Monitor     [engine.read]
│   └── /dashboard/trading/replay/[tradeId] Trade Replay [trades.read]
├── /dashboard/subscriptions          Subscriptions      [subscriptions.read]
├── /dashboard/payments               Payments           [billing.read]
├── /dashboard/promotions             Promotions         [role owner/admin] (no perm exists, §13.6)
├── /dashboard/news                   News & Calendar    [role owner/admin] (no perm exists, §13.6)
├── /dashboard/ea-builds              EA Builds          (CONTRACT GAP §13.2 — placeholder + marker)
├── /dashboard/telegram               Telegram           [telegram.send]    (CONTRACT GAP §13.3)
├── /dashboard/tickets                Support Tickets    [tickets.read]
│   └── /dashboard/tickets/[ticketId]
├── /dashboard/notifications          Notifications      [emails.read]      (partial gap §13.4)
├── /dashboard/system                 System Health      [system.health.read]
├── /dashboard/audit                  Audit Logs         [audit.read]
├── /dashboard/roles                  Roles & Permissions [roles.read]
├── /dashboard/users                  Users              [users.read]
├── /dashboard/security               Security (own account)  [self.*]
├── /dashboard/settings               Settings           [system.settings]
└── /dashboard/revenue                Revenue            [owner-only nav; owner-candidate §10.3]
```

Legacy standalone `/users`, `/licenses`, `/health`, `/audit`, `/accounts`, `/accounts/[id]` are folded
into the tree above; their old paths are kept as **temporary redirects** (via `next.config`) to the new
`/dashboard/*` equivalents (DECIDED).

### 4.3 Component architecture
- `app/login`, `app/forbidden`, `app/(dashboard)/` route group with `layout.tsx` → `AdminSidebar` + `AdminTopbar` + `UserMenu` (alternatively `app/dashboard/layout.tsx`; final choice at build, keep the existing flat `/dashboard` pattern).
- `components/auth/AdminAuthGuard.tsx` — SSR+CSR guard: resolves `/auth/me`, redirects to `/login` when unauthenticated, `/forbidden` when role lacks the page gate.
- `components/auth/RequirePermission.tsx` — per-page/action check against `POST /auth/check-permission`; renders a fallback or `403` view. Backend remains authoritative.
- `components/layout/*` — sidebar (permission-filtered nav from `lib/permissions.ts`), topbar with health + audit shortcut, user menu.
- `components/ui/*` and `components/shared/*` — reuse proven patterns from `client_dashboard/` (DataTable, ConfirmDialog, Toast, Skeleton, EmptyState, StatusBadge, Pagination).
- `lib/api.ts` — typed JWT admin client only; **remove** legacy aliases (`listAccounts`, `getRecentAudit`, …).
- `lib/permissions.ts` — nav config: each item declares its `permission` + fallback role; labels are English-only.
- `lib/constants.ts` — frozen metric enums, severities, license/subscription status maps (single source, mirrored from backend docs, not logic).

### 4.4 API / service layer (frontend only)
- Server components read frozen `/api/admin/*` endpoints via the JWT client; client components mutate via authorized POST/PATCH under `RequirePermission`.
- No frontend replica of `ROLE_PERMISSIONS`; access decisions come from `/auth/me` (role) + `/auth/check-permission`. This is the allowed use of `check-permission` ("keep only if frontend needs it").

---

## 5. RBAC Model

### 5.1 Terminology
- **Role** — assigned to a user; e.g. `owner`, `admin`, `support`.
- **Permission** — a `resource.action` string from the `Permission` enum; the unit of authorization.
- **Resource** — the noun in the permission (`clients`, `accounts`, `licenses`, `trades`, …).
- **Action** — the verb (`read`, `create`, `update`, `delete`, `suspend`, `activate`, `export`, `control`, …).
- **Scope** — data visibility: CLIENT = own data only; ADMIN = operational data per assigned permissions;
  OWNER = unrestricted control plane.

### 5.2 Authoritative permission set (`security/access_control.py`, verified)
`clients.read/create/update/delete/suspend/activate/export`; `accounts.read/create/update/delete`;
`subscriptions.read/create/update/cancel`; `licenses.read/create/update/delete`;
`trades.read/export/view`; `analytics.read`; `engine.read/start/stop/restart/control`;
`roles.read/create/update/delete/assign`; `users.read/create/update/delete`;
`billing.read/create/refund`; `support.read/create/reply`; `tickets.read/update/ban`;
`telegram.send`; `emails.read/send`; `audit.read`; `health.read`; `admin.dashboard.read`;
`admin.overview`; `system.health.read/update`; `system.settings`; `system.secrets`;
`self.read/update`; `owner = "*"`.

### 5.3 Naming note (do NOT invent permissions)
The aspirational names in the plan (`clients.view`, `clients.manage`, `builds.view`, …) do **not** exist in
the enum. This spec maps intent onto real values: `clients.view → clients.read`,
`clients.manage → clients.update` (plus per-action perms), `trades.view → trades.read`,
`support.manage → support.reply`, etc. `builds.*` and `system_health.view` do not exist (§13).

### 5.4 Surface → permission matrix (minimum gate, verified against `ROLE_PERMISSIONS`)
| Surface | View | Key actions | Held by (default) |
|---|---|---|---|
| Overview | `admin.overview` | — | admin, owner |
| Clients | `clients.read` | create/update/suspend/activate/export | admin (all); support/billing/notification_mgr/risk_manager (read) |
| Client Details | `clients.read` | per-action above | same; **hard delete = `clients.delete`, NOT held by admin** → owner-only UI |
| Licenses | `licenses.read` | create/update/delete | admin |
| MT5 Accounts | `accounts.read` | create/update/delete | admin; read for support/risk_manager/analyst — **no JWT API (§13.1)** |
| Trades | `trades.read` | close-symbol → `engine.control`; export → `trades.export` | admin; read for support/risk_manager/analyst |
| Performance | `analytics.read` | — | admin, risk_manager, analyst |
| Subscriptions | `subscriptions.read` | update/cancel | admin; update for billing |
| EA Builds | — | — | **no permission, no endpoint (§13.2)** |
| Telegram | `telegram.send` | — | admin, notification_mgr — **no working endpoint (§13.3)** |
| Support Tickets | `tickets.read` | reply → `support.reply`; ban → `tickets.ban` | admin; read+reply for support |
| Notifications | `emails.read` | send → `emails.send`/`telegram.send` | admin, notification_mgr — **no delivery contract (§13.4)** |
| System Health | `system.health.read` | update → `system.health.update` | admin |
| Audit Logs | `audit.read` | — | admin (support does NOT hold audit.read) |
| Security (own) | `self.read` | 2FA/sessions/password via `/auth/*` | any authenticated user |
| Settings | `system.settings` | — | admin; **`system.secrets` NOT held by admin → never rendered** |

### 5.5 Role → surface guidance (defaults; DB RolePermission rows may override)
| Aspirational | Current role | Default surfaces |
|---|---|---|
| OWNER | `owner` (wildcard) | everything incl. secrets + revenue |
| ADMIN | `admin` | full ops except `clients.delete`, `billing.refund`, `system.secrets` |
| SUPPORT | `support` | clients/accounts/trades read, health, tickets read+update, support read+reply |
| ANALYST | `analyst` | trades/analytics/accounts read |
| FINANCE | `billing` (conceptual; do not rename) | billing read/create/refund, subscriptions read+update, clients read |
| DEVELOPER | **does not exist — do not seed** | future target set documented in §10.2 |

### 5.6 Frontend authorization design (no duplication of business logic)
- Backend `require_permission` is the **only** enforcement point (403 → central handler → `/forbidden`).
- Frontend uses `/auth/me` (role) for coarse nav filtering and `POST /auth/check-permission` for
  page/action-level gates. This mirrors existing permissions without re-implementing `ROLE_PERMISSIONS`.

---

## 6. API Contract Mapping (page → frozen endpoint)

| Page | Endpoint(s) | State |
|---|---|---|
| Overview | `GET /api/admin/overview` (+ `audit-logs/summary`, `trading/overview` composed client-side) | frozen + golden |
| Clients | `GET /api/admin/clients`; create/update/suspend/activate/export | frozen |
| Client Details | `GET /api/admin/clients/{client_id}` | frozen, **currently unused → wire it** |
| Licenses | `GET /api/admin/licenses` (+ detail `GET /api/admin/licenses/{license_id}`) | frozen |
| MT5 Accounts | **none (JWT)** | **GAP §13.1** |
| Trades | `GET /api/admin/trading/trades`; close → `POST /api/admin/trading/control/close-symbol` | frozen (control unused → wire) |
| Performance | `GET /api/admin/trading/stats/{interval}` | frozen |
| Signals / Risk / Engine | `GET /api/admin/trading/{signals,risk,engine}` | frozen |
| Trade Replay | `GET /api/admin/trading/replay/{trade_id}` + `GET /api/admin/trades/{trade_id}/snapshot` | frozen (snapshot = canonical path, unused → wire) |
| Subscriptions | `GET /api/admin/subscriptions`; `PATCH /api/admin/subscriptions/{sub_id}` | frozen (PATCH unused → wire) |
| Payments | `GET /api/admin/billing/…` (as defined by billing router) | frozen |
| Promotions / News | `GET/POST …/api/admin/promotions*`, `…/news*` | frozen; **role-gated only** (§13.6) |
| EA Builds | **none (admin)** | **GAP §13.2** |
| Telegram | **none working** | **GAP §13.3** |
| Support Tickets | `GET /api/admin/tickets*`; reply/update; `GET /api/admin/tickets/{ticket_id}` (detail unused → wire) | frozen |
| Notifications | settings toggles only | **partial GAP §13.4** |
| System Health | `GET /api/admin/system-health*` (+ `GET /api/admin/system-health/summary`, unused → wire); `POST …/api/restart` | frozen; **restart is a stub → hide action until approved** |
| Audit Logs | `GET /api/admin/audit-logs` + `GET /api/admin/audit-logs/summary` | frozen (verified working; replaces broken `/admin/audit`) |
| Roles | `GET /api/admin/roles*` (+ check-permission) | frozen |
| Users | `GET/POST …/api/admin/users*` | frozen |
| Security (own) | `/auth/me`, `/auth/2fa/*`, `/auth/sessions/*`, `/auth/change-password` | frozen |
| Settings | `GET/PUT /api/admin/settings*`, site settings | frozen |

Legacy `/admin/*` (X-Admin-Token) calls are **removed** from the frontend (§13.5).

---

## 7. Security Model
- Auth: same JWT flow as Client Portal (`/auth/login`, staff 2FA step, refresh).
- Authorization: backend `require_permission` authoritative; frontend gates are UX only (§5.6).
- **Secrets:** never render `system.secrets`-gated data; admin role does not hold it. No SMTP password,
  broker credential, JWT secret, or DB credential may be printed anywhere.
- The legacy `ADMIN_TOKEN` must never reach the browser; `NEXT_PUBLIC_ADMIN_TOKEN` usage is removed.
- All mutating actions carry a confirm step (§9) and are server-audited (§8).

## 8. Audit Requirements
- Audit remains **server-side** via `log_event`/`AuditLog`; the frontend adds no audit.
- Admin Portal exposes the existing audit trail at `/dashboard/audit` (`GET /api/admin/audit-logs`).
- Sensitive actions already audited server-side: login, license ops, user/role changes, engine control,
  settings writes, ticket updates, 2FA changes, session revoke.
- Password/token values are never logged (existing backend contract).

## 9. UX Requirements
- Loading skeletons, empty states, error boundaries; central 403 → `/forbidden`, 401 → `/login`.
- Every dangerous action (suspend/ban/delete/engine control/settings write/restart) requires a typed-or-click ConfirmDialog; mutations show pending + rollback on failure.
- Server-side pagination where the endpoint supports it; client-side sort/filter only on fetched pages.
- StatusBadges for license/subscription/account/ticket states (mapped in `lib/constants.ts`).
- Responsive down to tablet; keyboard-accessible; English-only (i18n out of scope).

## 10. Future Owner Boundary & Role Compatibility
### 10.1 Compatibility guarantee
Admin Portal V2 is implemented so the future Owner Portal can take over control-plane surfaces without
rewrites: it adds no new roles, no new permissions, no endpoint, and does not gate anything on
"is this the admin app".

### 10.2 Future `developer` role (documented only, NOT seeded)
Target future permission set (for when policy is approved): `engine.read/control`, `system.health.read/update`,
`system.settings`, `trades.read`, `audit.read`, `roles.read`, `health.read`, `admin.overview`.

### 10.3 Owner-candidate surfaces
`/dashboard/revenue` (uses `GET /api/admin/analytics/revenue`) is exposed in nav to `owner` only and must
NOT be extended in Phase 4; it migrates to `owner.ictfundedeapro.com` later. `system.secrets`-gated
settings remain owner-only by permission.

## 11. Migration Plan (`admin_dashboard/` → pure Admin Portal)
1. **Backup** (not a git repo): copy `admin_dashboard/` to `%TEMP%\opencode\admin_dashboard_phase3_backup`.
2. Delete client pages `app/client/**` (superseded by `client_dashboard/`).
3. Delete `lib/client-auth.ts`, `lib/client-api.ts`, `components/ClientSidebar.tsx`, `components/auth/client_guard.tsx`.
4. Simplify `auth_guard.tsx`: PUBLIC = `/login`, `/forbidden`; remove client branches; keep admin 2FA step.
5. Fix `/login` cross-links (point to admin `/forgot-password`; remove client link).
6. Add `app/(dashboard)/layout.tsx` (or `app/dashboard/layout.tsx`) with `AdminSidebar`/`AdminTopbar`.
7. Fold legacy `/users`, `/licenses`, `/health`, `/audit`, `/accounts`, `/accounts/[id]` into `/dashboard/*`;
   keep old paths as **temporary redirects** via `next.config` (DECIDED).
8. Rewrite `lib/api.ts`: drop legacy aliases; add typed wrappers for every frozen endpoint in §6 (wiring currently-unused ones: client detail, license detail, ticket detail, subscription PATCH, system-health summary, trade snapshot, close-symbol).
9. Delete dead `components/Sidebar.tsx`.
10. Rebuild `lib/permissions.ts` nav with permission tags + `RequirePermission`.
11. Add EA Builds / Telegram placeholder pages with explicit "contract gap — pending backend" markers (no fake data).
12. Remove `NEXT_PUBLIC_ADMIN_TOKEN` usage from env/build; keep `NEXT_PUBLIC_API_URL`.
13. Verify: build, typecheck, QA suite (§12), regressions. Rollback = restore backup.

## 12. QA Plan
- Frontend: `next build` + `tsc --noEmit` for `admin_dashboard/`.
- New `scripts/_qa_admin_portal.py` (backend smoke, no new code — assertions only):
  - admin login + staff 2FA flow;
  - permission spot checks: client token → 403 on `/api/admin/overview`; support → tickets/clients OK, `/api/admin/settings` + `/api/admin/audit-logs` 403; billing → billing/subscriptions OK, engine 403; analyst → analytics OK, engine 403;
  - contract smoke per §6 endpoint (expected status + shape; overview reuses the golden master);
  - regression guard: legacy `/admin/*` returns 401 without `X-Admin-Token`.
- Existing suites must stay green: auth 22, sprint1 54, sprint2 62, wizard 13, portal 53, anchor, phase2 email, golden masters.
- Manual/E2E checklist: login→overview→clients detail→license→ticket→audit→settings happy paths + forbidden flows.

## 13. Known Contract Gaps (verified — STOP, do not implement)
1. **MT5 Accounts admin API (JWT): none exists.** Only legacy `/admin/accounts*` (X-Admin-Token). The current UI calls them with JWT → 401. → Accounts surface renders a "contract gap — pending backend" marker; no new endpoint.
2. **EA Builds admin management: no endpoint** (only client-side `/api/client/ea*`). → placeholder page + marker.
3. **Telegram management/broadcast: no working endpoint.** `news broadcast` references a missing `telegram_service`; `restart_service` is a stub. Permission `telegram.send` exists but has nothing to call. → placeholder + marker.
4. **Admin Notifications delivery: none.** Only settings toggles (email/telegram) exist. → read-only toggles + marker for delivery.
5. **Legacy `/admin/*` static-token routers** remain frozen; Phase 4 frontend stops calling them. Final backend cleanup of those routers is a separate, explicitly approved task — not this phase.
6. **No `news.*` / `promotions.*` permissions exist** in the enum; those routers are gated by role (owner/admin). Verify exact gating at build time; do not invent permissions.
7. **`/api/admin/dashboard` aggregator does not exist and is forbidden by freeze** → Overview composes frozen endpoints client-side.

## 14. Out of Scope
Owner Portal, `developer` role seeding, all backend changes, Telegram implementation, Billing implementation,
coupons, MT5/EA-build/notification backend contracts, deployment/DNS/VPS, Website W1 redesign,
Client Portal changes, Trading Engine changes, admin i18n (English-only).

## 15. Deliverables (on approval)
- Restructured `admin_dashboard/` (24 admin pages, §4.2) with permission-gated nav.
- `lib/api.ts` typed JWT client wiring the frozen contracts in §6.
- `AdminAuthGuard` + `RequirePermission`; legacy aliases and client pages removed.
- `scripts/_qa_admin_portal.py`; all QA/regressions green.
- `docs/phase4_admin_dashboard_implementation_report.md` (post-implementation).

## 16. Open Questions (resolved)
- **Contract-gap surfaces (MT5 Accounts, EA Builds, Telegram, Notifications):** DECIDED — build routes now with an explicit "Backend contract pending" marker; wire when a backend contract is approved.
- **Legacy standalone paths:** DECIDED — temporary redirects to new `/dashboard/*` equivalents.
- **`/dashboard/revenue`:** DECIDED — kept in admin nav, owner-only, not extended (migrates to Owner Portal later).
- **Admin language:** DECIDED — English-only for Phase 4; no i18n in this phase.
- **Authentication:** DECIDED — reuse the existing frozen `/auth/*` JWT flow + existing staff 2FA for Admin. No new auth system, no duplicate login/token/session logic. Client and Admin share the same auth infrastructure; authorization boundaries differ. Future Owner reuses the same foundation.
- **Authorization source of truth:** DECIDED — `security/access_control.py` remains authoritative (`Permission`, `ROLE_PERMISSIONS`, `ROLE_HIERARCHY`, `has_permission`). No new permissions where an existing one is reusable; the enum is not renamed or mutated this phase. Future Owner/Developer/Support/Finance roles remain architecturally possible without being implemented now.

## 17. Next Move
**APPROVED — proceed to implementation** (see implementation report at completion). At completion: STOP; do not start Phase 5 automatically.
