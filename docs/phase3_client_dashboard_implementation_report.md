# Phase 3 — Client Portal Implementation Report

Status: **Complete** (no deployment, no next phase)

Scope approved in `docs/phase3_client_dashboard.md`. This phase delivered a standalone
client portal (`client_dashboard/`) that consumes the frozen Backend V2 contracts, with the
single recorded backend permission-scope correction for client 2FA (spec §0.7).

---

## 1. Objective

Deliver the Phase 3 Client Portal as a **separate Next.js application** (`client_dashboard/`,
target `https://app.ictfundedeapro.com`) that:

- gives clients self-service access to their own account/license/subscription/trading data,
- implements full client auth and security (including self-managed 2FA + sessions),
- is strictly isolated from admin/owner surfaces (a staff token never renders the portal),
- consumes only the frozen Backend V2 endpoints (no speculative endpoints added),
- ships with a QA suite covering auth, 2FA, isolation, and empty states.

---

## 2. Backend Change (the only permitted one)

Spec §0.7 recorded permission-scope correction, applied to `api/routes/auth_router.py`:

- `POST /auth/2fa/setup` — removed staff-only guard (password re-authentication retained).
- `POST /auth/2fa/enable` — removed staff-only guard.
- `POST /auth/2fa/disable` — removed staff-only guard.
- Deleted the now-unused `STAFF_ROLES` set and `_is_staff()` helper.

No endpoint, DTO, or verification logic was changed. `python -m py_compile` passes.
The regression suite (below) proves a **non-staff client** can complete the full 2FA cycle
and that no other user's 2FA is touched.

No other backend, database, engine, Telegram, billing, or Trading Engine change was made.

---

## 3. Portal Application (`client_dashboard/`)

Scaffold: Next.js 15.2 + React 19 + Tailwind 4 + `lightweight-charts` 5.2, path alias `@/*`,
`output: "standalone"`. Design tokens are mirrored from the approved design system (same CSS
variables, `.card`, `.page-title`, `.section-title`, `.btn*`, `.input` classes); dark/light
theme persists via `localStorage("theme")` with server preferences driving the default.

### Data / auth layer

- `lib/auth.ts` — login (incl. `two_factor_required` step), verify2FA, register, refresh,
  logout/logout-all, `authFetch` with 401→refresh→retry, forgot/reset/change password,
  `getMe`, `setup2FA` / `enable2FA` / `disable2FA`, `listSessions` / `revokeSession`.
  Storage keys `client_at` / `client_rt` / `client_user` (isolated from admin).
- `lib/api.ts` — typed fetchers for every consumed self-scoped endpoint: dashboard, profile,
  license, subscription (cancel/renew), trades, performance, settings, accounts CRUD +
  disconnect/reconnect, Telegram status (read-only), EA builds/download.

### Guards, layout, shared UI

- `components/ClientAuthGuard.tsx` — public routes (`/login`, `/register`,
  `/forgot-password`, `/reset-password`, `/verify-email`, `/forbidden`); unauthenticated →
  `/login`; staff role → `/forbidden`; unverified email → `/verify-email`.
- `components/ClientSidebar.tsx` + `app/dashboard/layout.tsx` — grouped navigation
  (Account / Trading / Manage / Account & Help), desktop sidebar + mobile topbar, theme
  toggle, logout.
- `components/ui.tsx` — `Notice`, `PageHeader`, `EmptyState`, `StatCard`, `InfoRow`, `Dot`,
  `StatusBadge`, `Loading`, `ErrorBox`.

### Pages (24 routes total; 15 portal surfaces)

| Surface | Route | Notes |
|---|---|---|
| Overview | `/dashboard` | status cards, today stats, equity curve (lightweight-charts), totals, recent signals/trades, quick actions |
| MT5 Accounts | `/dashboard/accounts` | list, add, rename, delete, disconnect/reconnect, no-license empty state |
| Account Details (new) | `/dashboard/accounts/[accountId]` | masked login, rename, reconnect (password in-memory only), remove, not-found |
| Trading Activity | `/dashboard/activity` | all/open/closed filter + full table |
| Performance | `/dashboard/performance` | stat grid, by-symbol, monthly P&L, equity bars |
| License | `/dashboard/license` | key, status, limits, bound account, days remaining, activation history |
| EA Downloads | `/dashboard/downloads` | latest build, changelog, version check, Windows download (macOS "coming soon") |
| Subscription | `/dashboard/subscription` | plan details, renew/cancel, plan cards (upgrade → Contact Support), invoices |
| Telegram (read-only boundary) | `/dashboard/telegram` | status card + bot link from `GET /api/client/telegram`; actions "coming soon" |
| Notifications (new) | `/dashboard/notifications` | preference toggles only (delivery deferred) |
| Settings | `/dashboard/settings` | language/timezone/theme, trading defaults, news filter, risk profile, notification flags |
| Security (new) | `/dashboard/security` | full client 2FA (setup/enable/disable) + active sessions (list/revoke) |
| Profile | `/dashboard/profile` | personal info + change password (signs out all sessions) |
| Support (placeholder) | `/dashboard/support` | contact channels |
| Billing (placeholder) | `/dashboard/billing` | payment-method/invoice placeholders pointing at Subscription |

Auth flow pages: `/login` (2-step: password then 6-digit authenticator code),
`/register`, `/forgot-password`, `/reset-password` (Suspense + `?code=` prefill on
`/verify-email`), `/forbidden` (staff-account blocked page), and role-aware `/` redirect.

### Design decisions

- **No backup/recovery-code system** (measured decision, per spec §15): recovery is the
  existing forgot-password/reset flow (which revokes sessions); device loss is a manual
  support flow.
- **Telegram read-only**: connect/disconnect/test exist server-side but UI wiring is
  deferred to the Telegram phase; notification preferences live on the Notifications page
  and reuse the same preference keys the Telegram page reads.
- **QR display** for 2FA setup uses the same qrserver.com image pattern already used by the
  admin Security page (site-consistent).

---

## 4. Verification

### Portal build

- `npm install` — OK (Node v24.11.1 / npm 11.6.2).
- `npm run typecheck` (`tsc --noEmit`) — **PASS**.
- `npm run build` (`next build`) — **PASS**; all 24 routes generated, no lint/type errors.

### Admin dashboard regression (untouched)

- `npm run build` in `admin_dashboard/` — **PASS** (all routes, incl. legacy client pages).

### Backend regression suites (QA DB `ict_funded_ea_qa`)

| Suite | Result |
|---|---|
| `scripts/_qa_auth_full.py` (auth + 2FA) | **22/22 PASS** |
| `scripts/_qa_client_sprint1.py` | **54/54 PASS** |
| `scripts/_qa_client_sprint2.py` | **62/62 PASS** |
| `scripts/_qa_wizard.py` | **13/13 PASS** |
| `scripts/_qa_anchor.py` | **ALL PASS** |
| `scripts/_qa_phase2_auth_email.py` | **PASS** |
| Golden masters (account / admin dashboard / client dashboard / license) `--mode compare` | **4/4 PASS** |
| `python -m py_compile api/routes/auth_router.py` | **PASS** |

### New portal QA — `scripts/_qa_client_portal.py`

**53/53 PASS**, covering the spec §13 plan:

1. **Unauthenticated guard** — all 10 client endpoints return 401 without a token.
2. **Register → verify → login** — client role + redirect `/client/dashboard`.
3. **Empty states** — fresh client: empty license, null subscription, empty accounts,
   zero-data dashboard.
4. **Settings/notifications/telegram preference validation** — invalid theme/notification
   keys → 400; valid saves persist (symbols uppercased).
5. **Isolation** — client A cannot rename/delete client B's account (404), cannot reach
   `/api/admin/overview` (403), and only sees its own data.
6. **Client 2FA full cycle (non-staff)** — setup → `two_factor_pending` → enable (wrong code
   rejected 401, correct TOTP accepted) → `two_factor_enabled` → login returns
   `two_factor_required` → verify (wrong 401 / correct OK) → disable (wrong 401 / correct OK)
   → 2FA fully off; client B's 2FA untouched.
7. **Sessions** — list, revoke own session, password change invalidates previous refresh
   token, login with new password.
8. **Staff redirect** — staff login targets the admin `/dashboard`, never the portal.

### Pre-existing failures (unrelated to this phase)

- `test_all.py` — stale import (`EVENT_EMOJI` no longer exists in
  `telegram_bot.services.alert_service`); fails before this phase's code.
- `tests/test_permissions.py` — 6/7; the hardcoded expected permission list predates
  `tickets.*` / `trades.view` permissions and was not updated. Neither file touches any
  code changed by this phase.

---

## 5. Security

- Secrets are environment inputs only; no token/key/password is hardcoded in the portal.
- Passwords are sent only over the login/setup/disable/change flows and never stored in
  `localStorage` (only JWT access/refresh + user profile snapshot are cached).
- Client data is strictly self-scoped server-side (`current_user.id`); the frontend never
  sends foreign ids.
- Broker passwords are handled in-memory only on the Account Details reconnect flow; the
  server stores them encrypted.
- Staff tokens render `/forbidden`, never portal content; client tokens are blocked from
  admin endpoints by backend permissions (403 verified).
- Every sensitive action is audited server-side (`auth.2fa_*`, `auth.session_revoked`,
  `auth.password_change`, `client.*`).

---

## 6. Remaining / Not Done (by instruction)

- No deployment, DNS, VPS, or infrastructure configuration.
- No Website W2, Admin V2, Owner, Billing backend, Telegram backend, Trading Engine, or
  MT4/MT5 engine work.
- No i18n implementation (structure supports it; translations are deferred).
- Real SMTP/email delivery and DNS/SPF/DKIM/DMARC remain manual infrastructure items.
- `a11y` axe/keyboard pass on the portal is a follow-up (spec §13 lists it for the Full E2E
  QA phase).

---

## 7. Rollback Procedure

- **Frontend:** remove the `client_dashboard/` directory; nothing else is affected.
- **Backend:** restore `api/routes/auth_router.py` to add back the staff-only guard on
  `/auth/2fa/setup|enable|disable` (re-add `STAFF_ROLES` + `_is_staff()`); no database or
  migration rollback required.
- Re-run `scripts/_qa_auth_full.py` and `scripts/_qa_client_portal.py` to confirm state.
