# Phase 5 — Owner Portal Implementation Report

**Status:** COMPLETE (feature-frozen). All QA green. Stopped; Phase 6 not started.
**Spec:** `docs/phase5_owner_portal_final.md` (APPROVED — decisions CLOSED)
**Date:** 2026-08-09

---

## 1. Summary

`owner_portal/` is now a standalone Next.js Owner Portal (target
`https://owner.ictfundedeapro.com`) consuming only frozen Backend V2
`/api/admin/*` + `/auth/*` contracts. It is a distinct platform control plane
(revenue, users & roles, full audit, system health, engine control, safe settings,
billing oversight, promotions, news) with strict owner-only access (OQ-4), shared
`/auth/*` JWT (OQ-2), safe-settings-only secret boundary (OQ-3), and no new
backend endpoints, schema changes, or business logic. No Phase 6 work started.

## 2. Deliverables (spec §15) — all complete

| Deliverable | Status |
| --- | --- |
| `owner_portal/` Next.js app (routes §3) with permission-gated nav + strict owner gate | Done |
| `lib/api.ts` typed JWT client for the owner contract subset | Done |
| `OwnerAuthGuard` + owner 2FA flow; secret deny-list in settings UI | Done |
| `scripts/_qa_owner_portal.py` | Done — **110/110 PASS** |
| All QA/regressions green | Done (Section 4) |
| `docs/phase5_owner_portal_implementation_report.md` | This file |

## 3. Architecture & Migration (spec §13)

- New standalone app `owner_portal/` (Next 15, React 19, Tailwind 4, TS 5.7,
  standalone output, `@/*` alias). `admin_dashboard/` untouched.
- **Route tree implemented** (spec §3, 13 routes):
  `/`, `/login`, `/forbidden`, `/dashboard`, `/dashboard/revenue`, `/dashboard/users`,
  `/dashboard/roles`, `/dashboard/audit`, `/dashboard/system`, `/dashboard/engine`,
  `/dashboard/settings`, `/dashboard/billing`, `/dashboard/promotions`,
  `/dashboard/news`. `/dashboard/overview-chart` (optional split-out) not created —
  not required by spec.
- **Auth (`lib/auth.ts`):** owner-keyed storage `owner_at` / `owner_rt` /
  `owner_user` (fully separate from admin keys); `login`, `verifyTwoFactor`,
  `getMe`, `refreshAccessToken`, `logout`, `clearAuth`. Shared `/auth/*` JWT
  model retained (OQ-2).
- **API client (`lib/api.ts`):** `authFetch` with 401 auto-refresh; typed wrappers
  for every frozen endpoint in spec §5 (overview, users + actions, roles + assign +
  permissions, audit-logs + summary, system-health + engines/heartbeat/report +
  engine control, trading engine monitor/logs + control actions, settings + schema,
  plans/subscriptions/payments/revenue, promotions CRUD, news CRUD + broadcast +
  engine-status, `checkPermission`).
- **Gates:** `OwnerAuthGuard` (PUBLIC = `/login`, `/forbidden`; owner role enforced
  via local check + live `/auth/me`; non-owner → `/forbidden`) and
  `OwnerPermissionGuard` (owner short-circuit + `POST /auth/check-permission`).
  Backend `require_permission` remains authoritative; frontend gates are UX-only
  (OQ-4).
- **Nav (`lib/permissions.ts`):** fixed owner groups (Overview / Commercial /
  Control Plane / Marketing) tagged with permissions.
- **Settings safety (OQ-3):** `sanitizeSettingsPayload` strips deny-listed keys,
  schema `is_secret` keys, and the `••••••••` masked placeholder before any
  `PUT /settings`; secret-only categories render read-only with masked values.
  `system.secrets` is **not** wired. Future Secret Management boundary documented
  only (spec §7.4).
- **Provisioning lock (OQ-1):** no owner-creation/promotion API — verified 403 in QA.
- `NEXT_PUBLIC_API_URL` only; no secrets in the repo.

### 3.1 Build route table (13 pages, `next build`)

`/`, `/_not-found`, `/login`, `/forbidden`, `/dashboard`, `/dashboard/audit`,
`/dashboard/billing`, `/dashboard/engine`, `/dashboard/news`,
`/dashboard/promotions`, `/dashboard/revenue`, `/dashboard/roles`,
`/dashboard/settings`, `/dashboard/system`, `/dashboard/users`.

## 4. QA Results

### 4.1 Owner Portal QA — `scripts/_qa_owner_portal.py`

110 checks: unauthenticated 401s, owner login + redirect `/dashboard` + `/auth/me`
role=owner, owner 2FA full cycle + logout (revoked refresh token rejected),
wildcard access (owner 200 on every §5 endpoint), non-owner rejection (client 403
on owner surfaces; support partial), provisioning lock (owner create/promote/
suspend/delete all 403), revenue via `billing.read`, settings boundary
(GET masks secrets, PUT returns decrypted → deny-list mandatory, deny-list covers
every schema `is_secret` key, safe writes audited), audit trail (owner actions
recorded), dangerous actions (engine control, trading control, news lifecycle +
broadcast — all audited), portal isolation + client boundary.
**TOTAL 110 | PASS 110 | FAIL 0 | ERROR 0.**

### 4.2 Existing regression suites — all green

| Suite | Result |
| --- | --- |
| Owner portal QA (`scripts/_qa_owner_portal.py`) | **110/110 PASS** |
| Admin portal QA (`scripts/_qa_admin_portal.py`) | **92/92 PASS** |
| Backend V2 golden masters (license, account, client dashboard, admin dashboard) | PASS (compare) |
| Auth 22 | 22/22 |
| Sprint 1 | 54/54 |
| Sprint 2 | 62/62 |
| Client portal 53 | 53/53 |
| Wizard 13 | 13/13 |
| Phase 2.2 email (mocked) | PASS |
| `tests/test_permissions.py` | **7/7 PASS** |
| Frontend: `owner_portal` `tsc --noEmit` + `next build` | clean, exit 0 |

### 4.3 Documented (unfixed) pre-existing debt

- `tests/test_db_repositories.py::test_all` fails at collection: `pytest-asyncio`
  plugin is not installed in the venv. Infrastructure issue unrelated to Phase 5;
  documented, not fixed without approval.

## 5. Approved Defect Fix (owner deny-list)

QA of the settings boundary exposed a defect in the Owner Portal's own
`SECRET_DENYLIST` (`owner_portal/lib/api.ts`): it listed `email.smtp_password`,
but the backend schema key is **`email.smtp_pass`**
(`api/services/site_settings.py`, the sole `is_secret` schema key). The dead
entry was corrected to `email.smtp_pass`. The QA invariant now enforces that the
deny-list covers every `is_secret` key served by `GET /api/admin/settings/schema`.
No backend change.

## 6. Contract Notes & Boundaries

1. **Plans/promotions reads are public** (`subscriptions.read` is granted to the
   client role — public catalog/marketing). Owner reads are 200; owner/admin
   writes (`POST /promotions`, `POST /plans/restore-defaults`, plan updates)
   require `subscriptions.update`. Verified in QA §4.
2. **Logout contract:** `POST /auth/logout` requires a body
   `{"refresh_token": ...}` and revokes the refresh session; the stateless access
   token is dropped client-side by `clearAuth()`. Refresh path verified dead after
   logout (401).
3. **Settings boundary (OQ-3):** `GET /settings` masks secret values
   (`••••••••`); `PUT /settings` returns decrypted values — the Owner UI never
   sends secret keys (deny-list + `is_secret` filtering + placeholder stripping),
   so secrets never reach the PUT contract.
4. **News broadcast:** consumes the frozen `POST /news/{id}/broadcast` contract
   (mock-telegram in QA). Real Telegram delivery remains "backend contract
   pending" per Phase 4 spec §13.3.
5. **Revenue:** Admin `/dashboard/revenue` kept functional during transition
   (OQ-5). Owner Portal is the canonical future surface; backend revenue contract
   untouched.
6. **Admin QA "owner system.secrets allowed (wildcard)"** remains true — the
   wildcard grants access, but OQ-3 forbids the Owner UI from wiring secrets.

## 7. Out-of-Scope Compliance

No owner provisioning API, no token/portal binding, no secret-management
implementation, no revenue permission changes, no legacy `/admin/*` cleanup,
no VPS/deployment/DNS, no production secrets, no Telegram/Billing/coupons, no
Trading Engine / MT4/MT5 changes, no schema changes, English-only. No Phase 6.

## 8. Next Move

Per spec §16: **STOP — Phase 5 complete.** Do not start Phase 6 automatically.
Rollback path: `owner_portal/` is additive; removing it restores pre-Phase-5
Admin behavior with no backend change.
