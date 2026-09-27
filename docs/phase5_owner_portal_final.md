# Phase 5 — Owner Portal Implementation Plan (FINAL)

**Status:** DECISIONS CLOSED — documentation complete. **Implementation NOT started.**
Wait for explicit implementation approval.
**Target:** `owner.ictfundedeapro.com` — independent frontend app `owner_portal/`.
**Based on:** `docs/phase5_owner_portal.md` (planning) + frozen Backend V2 `/api/admin/*` + `/auth/*` contracts.

---

## 1. Approved Decisions (ALL CLOSED)

| OQ | Decision | Status |
| --- | --- | --- |
| **OQ-1 Owner provisioning** | Script-only (`scripts/seed_auth.py`). No owner-creation / owner-promotion API. Future provisioning = separate security phase. | **CLOSED** |
| **OQ-2 Token / portal binding** | Keep shared `/auth/*` JWT model. No portal-bound JWTs. Security = authentication + role/permission authorization + strict portal routing + asset/data isolation. Do not weaken role checks. | **CLOSED** |
| **OQ-3 Secrets** | **NEVER expose decrypted secrets via Owner Portal.** Do NOT use settings response as a secret-management interface. Do NOT wire `system.secrets` to the Owner UI in Phase 5. `system.settings` may be consumed only for safe/non-sensitive configuration. Document a future dedicated Secret Management boundary. No backend secret-management implementation in Phase 5. | **CLOSED** |
| **OQ-4 Portal access** | Strict owner-only portal. Non-owner denied/redirected. Enforce via existing backend authorization (not frontend hiding alone). | **CLOSED** |
| **OQ-5 Revenue migration** | Keep `/dashboard/revenue` in Admin during transition. Do not delete the revenue backend contract. Owner Portal becomes the canonical future revenue surface. Admin revenue UI removed/hidden only in a later explicit migration/deployment step. | **CLOSED** |
| **OQ-6 Revenue ownership** | Accept existing `billing.read` permission. No new revenue permission. Owner wildcard remains authoritative. | **CLOSED** |

### Phase 5 general rules (binding)
- Separate frontend app **`owner_portal/`** → `https://owner.ictfundedeapro.com`, independent from `website/`, `client_dashboard/`, `admin_dashboard/`.
- Reuse frozen Backend V2 contracts wherever possible. No duplicated business logic.
- No speculative endpoints. No DB schema changes. No Trading Engine / MT4 / MT5 / Telegram / Billing work. No VPS/deployment/DNS. No production secrets.
- Phase 5 must not become a reason to modify frozen Backend V2 unnecessarily.

---

## 2. Target Information Architecture

Owner Portal = **platform control plane**: global visibility, revenue, control-plane
operations, and future administration. It is **NOT** an admin with more permissions —
it is a distinct portal with distinct responsibilities.

```
owner.ictfundedeapro.com  →  Owner Portal  (platform control)
admin.ictfundedeapro.com  →  Admin Portal  (operational management)
app.ictfundedeapro.com    →  Client Portal (own data)
www.ictfundedeapro.com    →  Public Website
api.ictfundedeapro.com    →  Shared API
```

Owner responsibilities: revenue, users & roles (control plane), audit (full), system
health, engine control (emergency stop), system configuration (safe subset), billing
oversight, news/marketing control. NOT in Owner portal: client detail management,
support ticket triage, MT5 account CRUD, EA builds, Telegram, notifications delivery,
coupons.

---

## 3. Route Tree (`owner_portal/`)

```
/                          → (redirect to /login if unauthenticated)
/login                     → OwnerLogin (shared /auth/login + 2FA step; owner-only)
/forbidden                  → access denied (non-owner / insufficient)
/dashboard                  → Owner Overview (KPI cockpit)
/dashboard/revenue          → Revenue & Analytics        (GET /api/admin/analytics/revenue)
/dashboard/users            → Users (control)            (GET/POST/PATCH/DELETE /api/admin/users*)
/dashboard/roles            → Roles & Permissions        (GET/POST/PATCH/DELETE /api/admin/roles*, /permissions, /roles/assign)
/dashboard/audit            → Audit Logs                 (GET /api/admin/audit-logs, /audit-logs/summary)
/dashboard/system           → System Health              (GET /api/admin/system-health*, /system-health/report)
/dashboard/engine           → Engine Control             (POST /api/admin/trading/control/*)
/dashboard/settings         → Safe Configuration         (GET/PUT /api/admin/settings, /settings/schema — non-secret only)
/dashboard/billing          → Billing Oversight          (GET/PUT /api/admin/plans*, /subscriptions*, /payments)
/dashboard/promotions       → Promotions                 (GET/POST/PATCH/DELETE /api/admin/promotions*)
/dashboard/news             → News & Broadcast           (GET/POST/PATCH/DELETE /api/admin/news*, /news/{id}/broadcast, /news/engine-status)
/dashboard/overview-chart   → (optional split-out of read-only trading/global KPIs)
```

Layout: single `app/(dashboard)/layout.tsx` (or `app/dashboard/layout.tsx`) with
`OwnerSidebar` / `OwnerTopbar`. Public = `/login`, `/forbidden`.

---

## 4. Permission / Security Model

### 4.1 Source of truth (frozen)
`security/access_control.py` remains authoritative. Owner role = wildcard `"*"`;
`has_permission` returns `True` unconditionally for owner. Owner passes every frozen
endpoint. All denial paths are audited by `require_permission`.

### 4.2 Portal-level gating
- `OwnerAuthGuard`: PUBLIC = `/login`, `/forbidden`. Enforce role via `/auth/me`
  (role claim) **and** `POST /auth/check-permission` where a specific permission gate
  is needed. Non-owner → redirect `/forbidden` (OQ-4 strict).
- Staff 2FA: owner logins must complete the 2FA step (shared flow, already verified in
  QA). Owner portal login page reuses the same step.
- Nav visibility uses permission tags (UX only); enforcement remains backend.
- Keys: `owner_at`, `owner_rt`, `owner_user` — kept separate from admin keys.

### 4.3 Cross-portal boundaries
- No token/portal binding (OQ-2 CLOSED). Isolation = distinct origins + role gating +
  backend enforcement. `owner.` and `admin.` never read each other's localStorage.

---

## 5. API Mapping (frozen contracts only)

| Route | Endpoint(s) | Backend gate | Owner role result |
| --- | --- | --- | --- |
| Revenue | `GET /api/admin/analytics/revenue` | `billing.read` | 200 (wildcard) |
| Users | `GET /api/admin/users`, `GET /users/{id}`, `POST`, `PATCH`, `DELETE`, `suspend`, `activate` | `users.*`, `clients.suspend/activate` | 200 (wildcard) |
| Roles | `GET/POST/PATCH/DELETE /api/admin/roles*`, `GET /permissions`, `POST /roles/assign` | `roles.*` + hierarchy | 200 (wildcard bypasses hierarchy) |
| Audit | `GET /api/admin/audit-logs`, `/audit-logs/summary` | `audit.read` | 200 |
| System Health | `GET /api/admin/system-health*`, `/system-health/report` | `system.health.read` | 200 |
| Engine Control | `POST /api/admin/trading/control/enable\|disable\|pause\|resume\|close-all\|close-symbol\|emergency-stop` | `engine.start/stop/control` | 200 (audited) |
| Settings (safe) | `GET /api/admin/settings`, `GET /settings/schema`, `PUT /settings` | `system.settings` | 200 — **consume non-secret keys only** (OQ-3) |
| Billing Oversight | `GET /plans`, `PUT /plans/{id}`, `POST /plans/restore-defaults`, `GET /subscriptions`, `PATCH /subscriptions/{id}`, `POST /subscriptions/{id}/cancel`, `GET /payments` | `subscriptions.*`, `billing.read` | 200 |
| Promotions | `GET/POST/PATCH/DELETE /api/admin/promotions*` | role-gated (owner/admin) | 200 |
| News | `GET/POST/PATCH/DELETE /api/admin/news*`, `/news/{id}/broadcast`, `/news/engine-status` | `admin.overview` | 200 |
| Overview | `GET /api/admin/overview` | `admin.overview` | 200 |

**No endpoint is added, modified, or removed in Phase 5.**

---

## 6. Revenue Surface (canonical future home)

- Owner `/dashboard/revenue` uses `GET /api/admin/analytics/revenue` (frozen,
  `billing.read` — OQ-6 CLOSED).
- Renders MRR/ARR, total revenue, active/total subscriptions, active licenses,
  connected accounts, total users, churn 30d, new users 30d, plan distribution.
- **Admin transition:** keep `/dashboard/revenue` in Admin during Phase 5 (OQ-5 CLOSED).
  The Admin UI is removed/hidden only in a later explicit migration/deployment step after
  Owner Portal verification. Backend revenue contract is never deleted.

---

## 7. System Configuration Boundaries (OQ-3 — security-critical)

### 7.1 What the Owner Portal may do
- Read settings schema (`GET /settings/schema`) and effective settings
  (`GET /settings` — secret values arrive **masked** `••••••••`; do not unmask).
- Update **non-secret, non-sensitive** keys only where the frozen `PUT /settings`
  contract supports them (appearance, trading parameters, renderer, symbols/timeframes/
  sessions, news provider/refresh, api TTLs, workers intervals).

### 7.2 What the Owner Portal MUST NOT do
- **Never display, copy, or write decrypted secrets** (SMTP password, JWT/encryption
  keys, broker credentials, DB credentials, API keys).
- **Never use the settings response as a secret-management interface.**
- **Never wire `system.secrets` to the Owner UI in Phase 5.**

### 7.3 Secret policy (UI-level guard, defense in depth)
- The settings UI filters keys: `is_secret` keys are excluded from edit; masked values
  are shown read-only if at all.
- A code-level deny-list prevents secret keys from ever being sent to `PUT /settings`.

### 7.4 Future Secret Management boundary (documented only — NOT implemented)
A future dedicated security phase, requiring: encrypted storage, masked values, explicit
authorization (`system.secrets`), audit logging, controlled write operations, and no
plaintext secret exposure. No backend secret-management implementation in Phase 5.

---

## 8. Audit Requirements

- Every owner action already produces `AuditLog` rows via frozen `log_event` calls
  (user/role changes, settings writes, engine control, plan/subscription changes).
- Owner Audit surface (`/dashboard/audit`) reads `GET /api/admin/audit-logs` +
  `/audit-logs/summary` with filters (actor/action/severity/date).
- Dangerous actions (see §9) show an explicit confirm step in the UI **before** the call;
  the audit trail is the record of truth.
- Never log passwords, tokens, or secret values.

---

## 9. Dangerous Actions (explicit confirmation + audit)

- Engine control: **enable / disable / pause / resume / close-all / close-symbol /
  emergency-stop** (`POST /api/admin/trading/control/*`).
- Role assignment / modification (`POST /roles/assign`, `PATCH/DELETE /roles/{id}`).
- User suspend / activate / delete (`POST /users/{id}/suspend|activate`, `DELETE /users/{id}`).
- Plan changes / restore defaults (`PUT /plans/{id}`, `POST /plans/restore-defaults`).
- Subscription cancel (`POST /subscriptions/{id}/cancel`).
- Settings writes (non-secret only, §7).
- News broadcast (`POST /news/{id}/broadcast`) — remains marked "backend contract
  pending" (Telegram gap §13.3 of Phase 4) until Telegram is implemented.

Each action: confirm dialog → call frozen endpoint → surface audit result.

---

## 10. Future Compatibility (Support / Developer / Finance)

- Architecture leaves room for future roles without rework:
  - **Developer role:** not seeded (Phase 4 spec §10.2 documented set: `engine.read/
    control`, `system.health.read/update`, `system.settings`, `trades.read`, `audit.read`,
    `roles.read`, `health.read`, `admin.overview`).
  - **Support / Finance (billing):** existing frozen roles already gated on the same
    endpoints; Owner portal surfaces are nav-scoped by role so they degrade cleanly.
- `owner_portal/` gate components use role + permission tags, so adding roles later
  requires no structural change.

---

## 11. Owner / Admin Separation

- Distinct apps: `owner_portal/` vs `admin_dashboard/`; distinct origins
  (`owner.` vs `admin.`).
- Distinct responsibilities: control plane vs. operational management.
- Shared: same API origin, same `/auth/*`, same frozen `/api/admin/*` contracts, same
  `lib/api.ts` wrapper *pattern* (each app ships its own copy — apps are standalone
  Next builds).
- No cross-app imports; no shared token storage.

---

## 12. QA Plan

Frontend:
- `tsc --noEmit` + `next build` for `owner_portal/`.

New `scripts/_qa_owner_portal.py` (assertions only, no new code):
- Owner login + 2FA cycle; `/auth/me` role=owner.
- Owner-only access: client/support/admin denied on owner surfaces; owner allowed on all
  §5 endpoints (200 + shape).
- `POST /auth/check-permission` contract spot checks.
- Dangerous-action authorization: owner emergency-stop / role assign / settings write are
  audited; non-owner denied.
- Settings safety: `GET /settings` masks secret keys; Owner UI deny-list prevents secret
  keys from reaching `PUT /settings`.

Regression guard (must stay green):
- Admin portal 92, golden masters (4), auth 22, sprint1 54, sprint2 62, portal 53,
  wizard 13, anchor, phase2 email, `test_permissions.py` (7/7).

---

## 13. Migration Plan

1. **Backup** (not a git repo): copy `admin_dashboard/` to
   `%TEMP%\opencode\admin_dashboard_phase4_backup` and note rollback paths.
2. Create `owner_portal/` Next app (owner-only) per §3-§5; do not touch `admin_dashboard/`.
3. Wire owner nav + gates; implement revenue surface (Admin copy remains in place — OQ-5).
4. Run `_qa_owner_portal.py` + full regression set; keep Admin revenue page functional.
5. **Later, explicit step (NOT Phase 5):** on deployment of `owner.`, hide/remove the
   Admin `/dashboard/revenue` nav entry and redirect owners to `owner.`. Backend revenue
   contract stays.
6. Rollback path: owner portal is additive; removing it restores the pre-Phase-5 Admin
   behavior with no backend change.

---

## 14. Out of Scope (Phase 5)

Owner provisioning API, token/portal binding, secret management implementation, revenue
permission changes, legacy `/admin/*` cleanup, VPS/deployment/DNS, production secrets,
Telegram, Billing, coupons, Trading Engine, MT4/MT5, schema changes, i18n (English-only).

---

## 15. Deliverables (on explicit implementation approval)

- `owner_portal/` Next.js app (routes §3) with permission-gated nav + strict owner gate.
- `lib/api.ts` typed JWT client for the owner contract subset.
- `OwnerAuthGuard` + owner 2FA flow; secret deny-list in settings UI.
- `scripts/_qa_owner_portal.py`; all QA/regressions green.
- `docs/phase5_owner_portal_implementation_report.md` (post-implementation).

## 16. Next Move

**STOP — documentation complete, no code changed.** Await explicit implementation
approval. Do not start Billing/Telegram/VPS automatically.
