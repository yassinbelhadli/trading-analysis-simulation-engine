# Phase 5 — Owner Portal V2 (Planning)

**Status:** PLANNING ONLY — no code changes in this phase.
**Predecessor:** `docs/phase4_admin_dashboard.md` (APPROVED, complete) + its implementation report.
**Target:** `owner.ictfundedeapro.com` — independent portal, distinct from Admin (`admin.`), Client (`app.`), Website (`www.`), API (`api.`).

---

## 1. Objective

Build an independent Owner (control-plane) portal at `owner.ictfundedeapro.com`,
reusing the same frozen Backend V2 `/api/admin/*` + `/auth/*` contracts already
consumed by Admin Portal V2. The Owner portal is the *principal* surface — the user
behind the business — with:

- full revenue / business analytics;
- control-plane operations (users & roles, system settings + secrets, audit,
  system health, engine control / emergency stop);
- cross-role oversight without duplicating day-to-day Admin surfaces.

The portal must be a **separate frontend app** (`owner_dashboard/`), NOT a route under
`admin.` or `app.` — enforced by distinct origins (subdomains), so a CSRF / session
mix-up between portals is architecturally impossible.

---

## 2. Current-State Inspection (verified 2026-08-08)

### 2.1 Owner role in `security/access_control.py` (frozen)

- `Permission.OWNER = "*"` (line 96) and `ROLE_PERMISSIONS["owner"] = {"*"}`.
- `has_permission` returns `True` **unconditionally** for role `owner`
  (lines 205-206) — no DB `RolePermission` rows are seeded for owner (seed skips `{"*"}`
  at lines 248-249, 279-280).
- `ROLE_HIERARCHY["owner"] = 100` — hierarchy checks (roles create/update/delete/assign,
  `api/routes/admin/roles.py`) let owner manage any role; owner is the only caller
  allowed to touch roles at its own level.
- **Implication:** every frozen `/api/admin/*` endpoint already accepts the owner token
  via wildcard. No backend change is required for the owner portal to read/act — the
  owner portal is a *frontend gating + presentation* problem over existing contracts.

### 2.2 Owner provisioning (gap)

- `/api/admin/users` **cannot** create an owner account and `/api/admin/users/{id}`
  cannot promote to owner (explicit 403s: `users.py` lines 182-183, 148-149).
- `/api/admin/users/{id}/suspend` and `/delete` refuse the last owner (lines 218-219,
  258-259). `/roles/assign` refuses demoting the last owner (roles.py lines 206-212).
- The only owner provisioning today is `scripts/seed_auth.py`, which seeds the first
  user with role **owner** (lines 46-54). In practice the current "admin" account IS an
  owner.
- **Decision needed (OQ-1):** how a *second* owner is provisioned (one-off script vs.
  an approved owner-gated provisioning endpoint). No decision ⇒ document the script
  path only.

### 2.3 Shared auth (`/auth/*`, frozen) — portal isolation facts

- Login (`POST /auth/login`), staff 2FA (`/auth/2fa/setup|enable|disable`,
  `POST /auth/verify-2fa-login`), `/auth/me`, refresh, logout/all, sessions,
  `POST /auth/check-permission` — all shared and already verified by Admin QA (92/92).
- JWT carries `sub` + optional `role` claim (jwt_handler.py lines 25-40); **tokens are
  not bound to a portal**. Authorization is decided per-request by role + permission
  against the DB (dependencies.py `get_current_user` → `has_permission`), and
  `require_permission` audits every denial.
- `get_current_admin_user` allows owner **or** admin; no owner-only dependency exists
  on any endpoint today (owner simply passes every permission).
- CORS is `allow_origins=["*"]` (main.py lines 49-55) — a new origin needs no backend
  change.
- **Implication:** the Owner portal authenticates with the same `/auth/*`, gates its
  UI on role + `POST /auth/check-permission`, and relies on backend enforcement. No new
  auth system, no new tokens, no token/portal binding (unless OQ-2 mandates it).

### 2.4 Owner-relevant frozen endpoints (all under `/api/admin/*`)

| Surface | Endpoint(s) | Backend gate | Notes |
| --- | --- | --- | --- |
| Revenue | `GET /analytics/revenue` | `billing.read` | MRR/ARR, total revenue (from `payment.*` audit logs), churn, plan distribution. **Not owner-only at API level** (billing role can read). |
| Payments | `GET /payments` | `billing.read` | Derived from `AuditLog` `payment.%` events — no payment table. |
| Plans / Subscriptions | `GET /plans`, `PUT /plans/{id}`, `POST /plans/restore-defaults`, `GET /subscriptions`, `PATCH /subscriptions/{id}`, `POST /subscriptions/{id}/cancel` | `subscriptions.read/update/cancel` | Plan editor + subscription lifecycle. |
| Promotions | `GET/POST/PATCH/DELETE /promotions*` | role-gated (owner/admin) | Marketing control. |
| News | `GET/POST/PATCH/DELETE /news*`, `POST /news/{id}/broadcast`, `GET /news/engine-status` | `admin.overview` (role-gated owner/admin) | Broadcast currently blocked by missing telegram backend (Phase 4 gap §13.3). |
| Users | `GET/POST/PATCH/DELETE /users*`, suspend/activate | `users.*` / `clients.suspend` / `clients.activate` | Owner cannot create/promote owner via API (2.2). |
| Roles | `GET/POST/PATCH/DELETE /roles*`, `GET /permissions`, `POST /roles/assign` | `roles.*` + hierarchy | Owner bypasses hierarchy; can manage all. |
| Audit | `GET /audit-logs`, `GET /audit-logs/summary` | `audit.read` | Filters: actor/action/severity/date. |
| System Health | `GET /system-health*`, `GET /system-health/report` | `system.health.read` | (Fixed by approved Phase 4 bug fix.) |
| Engine control | `POST /trading/control/enable\|disable\|pause\|resume\|close-all\|close-symbol\|emergency-stop` | `engine.start/stop/control` | **Critical owner surface** — emergency-stop & close-all. |
| Trading read | `GET /trading/overview\|active-trades\|history\|signals\|risk\|performance\|engine\|engine/logs`, `GET /trading/trade/{id}/snapshot` | `trades.read` / `engine.read` / `trades.view` | Read-only oversight. |
| Settings | `GET/PUT /settings`, `GET /settings/schema` | `system.settings` | GET masks secrets; **PUT response returns decrypted secrets** (settings.py line 73). Admin currently holds `system.settings`. |
| Secrets | — | `system.secrets` | Permission **exists in enum but is not wired to any endpoint** (verified: no `SYSTEM_SECRETS` usage outside the enum). Reserved. |

### 2.5 Admin Portal current owner handling (to migrate, not duplicate)

- `/dashboard/revenue` nav is owner-only (frontend gate) and displays
  "Owner-candidate surface … migrates to the Owner Portal later" — ready to migrate
  wholesale.
- `/dashboard/security` (settings surface) is admin-gated at the backend
  (`system.settings`) and already shown to admin; the Owner portal adds a *true*
  secrets surface only if a secrets-gated endpoint is approved (OQ-3).
- `lib/permissions.ts` nav model (role + permission tags, `RequirePermission` as UX-only
  gate) is the pattern the Owner portal will copy.

---

## 3. Target Architecture

### 3.1 App boundary

- New Next.js app: **`owner_dashboard/`** (mirrors `admin_dashboard/` structure).
- Origin: `owner.ictfundedeapro.com` → distinct from `app.`, `admin.`, `www.`, `api.`.
- Reuses the same API origin (`api.ictfundedeapro.com`), the same `/auth/*` flow, and
  the same `/api/admin/*` frozen contracts.
- No new backend; no new permissions; no new endpoints; no schema changes.

### 3.2 Owner surfaces (control-plane scope)

Proposed nav (English-only, consistent with Phase 4):

1. **Dashboard / Overview** — KPIs (revenue, active subs, active licenses, connected
   accounts, engine status, alerts). Composes frozen endpoints client-side.
2. **Revenue & Analytics** — migrated from Admin `/dashboard/revenue`
   (`GET /api/admin/analytics/revenue`).
3. **Users & Roles** — `/api/admin/users*`, `/api/admin/roles*`, `/api/admin/permissions`.
4. **Audit** — `/api/admin/audit-logs`, `/summary` with filters.
5. **System Health** — `/api/admin/system-health*` + `/report`.
6. **Engine Control** — `POST /api/admin/trading/control/*` (start/stop/pause/resume,
   close-all, close-symbol, **emergency-stop**) with confirmation UX + audit display.
7. **Settings & Secrets** — settings schema / effective settings (masked); secrets
   surface gated by the reserved `system.secrets` permission if OQ-3 approves a wired
   endpoint; otherwise settings only.
8. **Billing Oversight** — plans editor, subscriptions, payments, promotions
   (read/write where the frozen contracts allow).
9. **News** — calendar + broadcast (broadcast stays marked "backend contract pending"
   per Phase 4 gap §13.3).

Explicitly NOT in the Owner portal (remain Admin duties, avoid duplication): client
management detail, support tickets, MT5 account CRUD, EA builds, Telegram, notifications
delivery, coupons.

### 3.3 Auth & gating in the portal

- `OwnerAuthGuard`: PUBLIC = `/login`, `/forbidden`; must be role `owner` (or check
  `admin.overview`? **Decision OQ-4** — strict owner-only vs. owner+admin-allow).
- Require 2FA step for owner logins (staff 2FA already proven in QA).
- `RequirePermission`-style component reuse for nav visibility; enforcement stays in
  backend.
- Keys: `owner_at`, `owner_rt`, `owner_user` (separate from admin keys to avoid
  cross-portal token confusion).

### 3.4 Component / file layout (mirror Admin Portal)

```
owner_dashboard/
  app/(dashboard)/ or app/dashboard/ layout + OwnerSidebar/OwnerTopbar
  lib/api.ts         (typed wrappers for the subset of frozen endpoints in 3.2)
  lib/permissions.ts (owner nav tags)
  components/auth/OwnerAuthGuard.tsx
  components/PermissionGuard.tsx (reuse pattern)
```

---

## 4. Hard Limits (same discipline as Phase 4)

1. No backend changes unless explicitly approved (see OQ-3 for the one candidate).
2. No new roles/permissions beyond the frozen enum; **no new endpoints**.
3. No schema changes; no data migration.
4. Legacy `/admin/*` static-token routers stay untouched and fail-closed.
5. English-only; no i18n this phase.
6. No deploy/DNS work in this phase (deployment is the separately-tracked VPS step).
7. Do NOT delete or restructure `admin_dashboard/` — it remains the day-to-day Admin
   portal. Only the owner-candidate surfaces are migrated/removed from Admin nav when
   the Owner portal lands (that migration is an implementation-time decision, OQ-5).

---

## 5. Reuse Rules

- Reuse `lib/api.ts` wrapper patterns and the `RequirePermission` gate pattern from
  `admin_dashboard/` (no cross-app imports; copy the pattern per codebase convention —
  the apps are standalone Next builds).
- Reuse the staff-2FA auth flow and `POST /auth/check-permission` contract as-is.
- Do not duplicate business logic; owner portal calls the same endpoints as Admin where
  the surface overlaps (revenue, audit, system-health).

---

## 6. Security Model (owner portal)

- Strict origin separation (subdomain) is the primary boundary.
- Owner login requires 2FA (enforced at the portal level; backend already supports).
- Secrets surface (if approved, OQ-3) must be owner-only at the backend gate —
  `system.secrets` — and the settings PUT response that today returns decrypted secrets
  to any `system.settings` holder should be narrowed or documented as a known risk.
- All dangerous actions (engine control, role assign, secret writes) trigger
  confirmation UX and are audited (`log_event` already writes audit rows; owner portal
  shows them in the Audit surface).
- Never log or store tokens; no `NEXT_PUBLIC_*` secrets.

---

## 7. QA Plan (Phase 5, at implementation time)

- `tsc --noEmit` + `next build` for `owner_dashboard/`.
- New `scripts/_qa_owner_portal.py` (assertions only):
  - owner login + 2FA cycle; `/auth/me` role=owner;
  - check-permission spot checks (owner allowed everywhere, client/support denied on
    owner surfaces);
  - contract smoke for every §3.2 endpoint with the owner token (status + shape);
  - dangerous-action authorization: owner emergency-stop (audited), role assign,
    settings write; non-owner denied;
  - regression guard: Admin portal QA and all Phase 4 suites stay green.
- Existing suites must remain green: admin portal 92, golden masters, auth 22, sprint1 54,
  sprint2 62, portal 53, wizard 13, anchor, phase2 email, `test_permissions.py`.

---

## 8. Known Gaps / Decisions (open — do not implement)

- **OQ-1 Owner provisioning:** no API can create a second owner; only
  `scripts/seed_auth.py`. Decide: document the script path (recommended) vs. approve a
  new owner-gated provisioning endpoint (backend change).
- **OQ-2 Token/portal binding:** tokens are currently portal-agnostic. A token minted on
  `admin.` is valid on `owner.`. Mitigation is origin separation + role gating. Decide:
  accept (recommended) vs. add an `audience`/issuer claim (backend change, frozen risk).
- **OQ-3 Secrets surface:** `system.secrets` is reserved but unwired; the settings PUT
  currently returns decrypted secrets to `system.settings` holders (admin). Decide:
  (a) owner portal shows settings only (no secrets UI, recommend); (b) approve wiring a
  `system.secrets`-gated read endpoint + narrowing settings PUT — a small, explicit,
  approved backend change documented like the Phase 4 `has_permission` fix.
- **OQ-4 Owner portal access:** strict owner-only vs. owner+admin allowed to open the
  portal. Recommend strict owner-only.
- **OQ-5 Migration of owner-candidate surfaces:** remove `/dashboard/revenue` from Admin
  nav once the Owner portal ships vs. keep both until the portal is production-ready.
  Recommend: keep Admin nav during Phase 5, remove at the deployment step.
- **OQ-6 Revenue ownership:** `/analytics/revenue` is gated by `billing.read` (billing
  role can read). Owner portal reads it via owner wildcard — no change. Decide whether to
  document as accepted (recommended).

---

## 9. Deliverables (Phase 5, on approval)

- `owner_dashboard/` Next.js app (owner surfaces per §3.2) with permission-gated nav.
- `lib/api.ts` typed JWT client for the owner contract subset.
- `OwnerAuthGuard` + owner 2FA flow; strict origin separation.
- `scripts/_qa_owner_portal.py`; all QA/regressions green.
- `docs/phase5_owner_portal_implementation_report.md` (post-implementation).

## 10. Next Move (this phase = planning only)

1. Review this document (OQ-1 … OQ-6).
2. On approval of the decisions, implement Phase 5 as a frontend-only phase per §3,
   with no backend change unless OQ-3(b) is approved.
3. At completion: STOP — do not start Billing/Telegram/VPS automatically.

**Planning complete — no code was changed.**
