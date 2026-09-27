# Phase 4 — Admin Dashboard Implementation Report

**Status:** COMPLETE (feature-frozen). All QA green. Stopped; Phase 5 not started.
**Spec:** `docs/phase4_admin_dashboard.md` (APPROVED)
**Date:** 2026-08-08

---

## 1. Summary

The `admin_dashboard/` Next.js app is now a pure Admin Portal consuming the frozen
Backend V2 `/api/admin/*` + `/auth/*` contracts over shared JWT auth. All 16 required
surfaces and the 24-page route tree (§4.2 of spec) are implemented, permission-gated,
and green against every regression suite. One pre-existing backend defect was found
during QA and fixed with explicit approval (Section 5).

## 2. Deliverables (spec §15) — all complete

| Deliverable | Status |
| --- | --- |
| Restructured `admin_dashboard/` (24 admin pages, spec §4.2) | Done |
| `lib/api.ts` typed JWT client wiring frozen contracts | Done |
| `AdminAuthGuard` + `RequirePermission`; legacy aliases + client pages removed | Done |
| `scripts/_qa_admin_portal.py` | Done — **92/92 PASS** |
| All QA/regressions green | Done (Section 4) |
| `docs/phase4_admin_dashboard_implementation_report.md` | This file |

## 3. Architecture & Migration (spec §11)

- Client pages (`app/client/**`), `lib/client-auth.ts`, `lib/client-api.ts`,
  `ClientSidebar.tsx`, `client_guard.tsx`, dead `Sidebar.tsx` removed.
- `auth_guard.tsx`: PUBLIC = `/login`, `/forbidden`; admin 2FA step kept.
- `app/dashboard/layout.tsx` + `AdminSidebar`/`AdminTopbar`.
- Legacy paths (`/users`, `/licenses`, `/health`, `/audit`, `/accounts`, `/accounts/[id]`,
  `/billing`, `/analytics`) now route into `/dashboard/*`; temporary redirects in
  `next.config.ts`. Spec-required `/dashboard/payments` created.
- `lib/api.ts`: legacy aliases dropped; typed wrappers for every frozen endpoint in
  spec §6 (overview, clients + detail, licenses + detail, subscriptions + PATCH,
  payments, promotions, news + engine-status, tickets + detail, users, roles,
  permissions, audit-logs + summary, system-health + summary/engines/heartbeat/report,
  settings + schema, trading overview/trades/history/signals/risk/performance/engine,
  revenue analytics, license/news CRUD actions).
- `lib/permissions.ts`: permission-tagged nav + `RequirePermission` (UX-only gates;
  backend `require_permission` remains authoritative).
- No raw `authFetch` remains in any `.tsx`. No `NEXT_PUBLIC_ADMIN_TOKEN` usage.
- Admin keys: `admin_at`, `admin_rt`, `admin_user`; `NEXT_PUBLIC_API_URL` only.

### 3.1 Build route table (spec §4.2, 24 pages)

`/`, `/login`, `/forbidden`, `/dashboard`, clients(+`[clientId]`), users, roles, security,
licenses, subscriptions, coupons, promotions, news, accounts(+`[id]` placeholder),
ea-builds (placeholder), telegram (placeholder), notifications, settings, audit, system,
trading(+trades/history/signals/risk/performance/engine/replay`[tradeId]`), payments,
revenue.

## 4. QA Results

### 4.1 Admin portal QA — `scripts/_qa_admin_portal.py`

92 checks: unauthenticated 401s (8 endpoints), admin login + staff 2FA cycle,
`/auth/check-permission` contract, permission spot checks (client/support/billing/
analyst/owner), contract smoke for every §6 endpoint (status + shape), dangerous-action
authorization (audited writes), legacy `/admin/*` fail-closed regression, client/admin
boundary. **TOTAL 92 | PASS 92 | FAIL 0 | ERROR 0.**

### 4.2 Existing regression suites (spec §12) — all green

| Suite | Result |
| --- | --- |
| Backend V2 golden masters (license, account, client dashboard, admin dashboard) | PASS (compare) |
| Anchor matrix (26 flagship scenarios) | ALL PASS |
| Auth 22 | 22/22 |
| Sprint 1 | 54/54 |
| Sprint 2 | 62/62 |
| Client portal 53 | 53/53 |
| Wizard 13 | 13/13 |
| Phase 2.2 email (mocked) | PASS |
| `tests/test_permissions.py` | **7/7 PASS** (was 6/7 stale — resolved by §5 fix) |
| Frontend: `admin_dashboard` `tsc --noEmit` + `next build` | clean, exit 0 |
| Frontend: `client_dashboard` `next build` | clean, exit 0 |

### 4.3 Documented (unfixed) pre-existing debt

- `tests/test_db_repositories.py::test_all` fails at collection: `pytest-asyncio`
  plugin is not installed in the venv. Infrastructure issue unrelated to Phase 4;
  documented, not fixed without approval.

## 5. Approved Backend Defect Fix (explicit approval)

QA exposed a pre-existing defect in `security/access_control.py` `has_permission`
(lines ~208-218): permission strings were split with `split(".")` (unbounded), so
`"system.health.read"` resolved to resource=`system`, action=`health` — but the seeder
stores it with `split(".", 1)` (resource=`system`, action=`health.read`). Every
non-owner role was therefore denied on `system.health.read` / `system.health.update`,
breaking the entire System Health page (a required Phase 4 surface).

**Fix (approved by user):** `has_permission` now splits with `split(".", 1)`, matching
the seeder. One-line semantic change; no other behavior altered. Verified by QA:
`/api/admin/system-health*` all 200 for admin; all regression suites remain green.

## 6. Known Contract Gaps (spec §13) — placeholders, STOP-compliant

1. **MT5 Accounts admin (JWT):** none — `/dashboard/accounts` renders "Backend contract
   pending" marker (`{"{client_id}"}` contract text); no invented endpoint.
2. **EA Builds:** placeholder page + marker.
3. **Telegram:** placeholder + marker; stub restart buttons removed from
   `/dashboard/system` (verified `restart_service` is a no-op stub).
4. **Notifications:** read-only toggles + delivery marker.
5. **Legacy `/admin/*` static-token routers:** frozen, not called by frontend, fail-closed
   (401/403 without `X-Admin-Token`) — regression-guarded in QA §7. Final cleanup remains
   a separate approved task.
6. **`news.*`/`promotions.*` permissions:** none in enum; routers gated by role
   (owner/admin) — verified, not invented.
7. **No `/api/admin/dashboard` aggregator:** Overview composes frozen endpoints
   client-side.

## 7. Out-of-Scope Compliance

No deploy/DNS/VPS, no Owner Portal, no `developer` role seeding, no Telegram/Billing
implementation, no MT5/EA-build/notification backend contracts, no Client Portal
changes, no Trading Engine changes, English-only, revenue owner-only (migrates to
Owner Portal later).

## 8. Next Move

Per spec §17: **STOP — Phase 4 complete.** Do not start Phase 5 automatically.
Rollback path if needed: restore `%TEMP%\opencode\admin_dashboard_phase3_backup`.
