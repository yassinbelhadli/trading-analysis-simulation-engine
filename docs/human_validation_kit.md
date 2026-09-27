# Human Validation Kit — Demo Accounts & Dev Email (P0-2 / P0-3 / P0-4)

The Human Validation Kit is the deliverable for the P0 items in
[`docs/product_readiness_audit.md`](product_readiness_audit.md):

- **P0-2** — no persistent demo accounts → fixed demo accounts exist.
- **P0-3** — email/verification blocked because SMTP is unconfigured → a
  development-only `EMAIL_TEST_MODE` mailbox unblocks the registration /
  verification / password-reset flows locally.
- **P0-4** — no 3-role walkthrough data → synthetic data covers the frozen
  backend contracts so every dashboard is non-empty.

Scope: **dev database only** (`ict_funded_ea`). Nothing here touches
production config, QA/golden databases, DNS, deployment, or external services.

---

## 1. Demo credentials

All demo accounts are `email_verified=True` with 2FA **disabled** — human
validation never depends on SMTP or authenticator apps.

| Role  | Email                              | Password           | Portal / redirect        |
|-------|------------------------------------|--------------------|--------------------------|
| Owner | `demo.owner@ict-ea-demo.dev`  | `OwnerDemo!2026`   | Owner portal :3002 → `/dashboard` |
| Admin | `demo.admin@ict-ea-demo.dev`  | `AdminDemo!2026`   | Admin portal :3001 → `/dashboard` |
| Client| `demo.client@ict-ea-demo.dev` | `ClientDemo!2026`  | Client portal :3000 → `/client/dashboard` |

These are local-dev credentials only. In any real deployment the seeded
accounts must be removed (see §5 Cleanup) and real accounts used instead.

---

## 2. Seed command (dev DB only)

```powershell
# from the project root, with the venv active
python -m scripts.seed_demo
```

- Requires PostgreSQL at the default dev URL
  (`postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea`)
  or `DATABASE_URL` pointing at a **dev** database.
- **Refuses to run** if the database name contains `_qa` or `_golden`.
- **Idempotent & deterministic**: every row uses a fixed UUID / unique key and
  is skipped if it already exists. Running it twice yields identical counts
  (this is asserted by the QA script, §7).
- Creates roles/permissions if missing (same as `seed_auth.py`).

What gets seeded for the demo client:

- License `ICT-DEMO-A1B2-C3D4` (plan `premium`, active, bound to the funded
  account, transfer-locked).
- Subscription (plan `premium`, monthly, active).
- 2 trading accounts: MT5 funded demo (`88001234`, 100k) and MT4 challenge
  demo (`66009876`, 50k) — both `verified`, `active`, `engine_status=ACTIVE`,
  `real_trading_enabled=False`.
- Account scans + risk profile (daily loss 500 / max loss 2000 / profit target
  8000, static drawdown).
- 5 planned signals (the client dashboard "recent signals" contract:
  `PaperTrade(status='PLANNED')`), 1 open trade, 6 closed trades (3 today —
  today/total stats are non-zero).
- Audit trail (logins, license activation, account connect, trade open/close,
  a WARNING risk stop). **No ERROR-severity entries in the last 24h**, so the
  admin overview "errors 24h" counter is not falsely triggered.
- 1 open support ticket, 1 published announcement, 2 upcoming high-impact news
  events, 1 non-latest EA build (`9.9.9-demo`, not downloadable), and a
  `demo.seed_version` site-setting marker.

## 3. Which data is synthetic

Everything created by the seed is fake:

- Emails/passwords above, prop firm "DemoProp LLC", broker "DemoProp Broker",
  MT logins `88001234` / `66009876`, balances/equities.
- All trades, prices, PnL, audit messages, ticket, news, and calendar events
  (`DEMO-FF-…` ids — they can never collide with real ForexFactory ids).
- The EA build `9.9.9-demo` is a placeholder, never `is_latest`, and is not
  downloadable.
- `encrypted_password` on trading accounts is **not** seeded — no broker
  password is stored or invented.

## 4. EMAIL_TEST_MODE (dev-only verification mechanism)

`config/.env` has empty `SMTP_USER`/`SMTP_PASS`, so `send_email` returns
False and verification/reset codes are created server-side but never
delivered. `EMAIL_TEST_MODE` fixes the local loop without SMTP.

**How it works** (`api/services/email_test_mode.py`):

1. Set `EMAIL_TEST_MODE=true` (environment variable, or in a local
   `.env`/PowerShell session — **not** in `config/.env`).
2. When `send_verification_email` / `send_password_reset_email` run, the code
   is written to the **clearly marked local dev mailbox**:
   `logs/dev_mailbox/mailbox.json` (newest last), instead of SMTP. The API
   then reports `verification_sent: true` and the normal client flows
   ("A new verification code has been sent…") proceed.
3. Open `logs/dev_mailbox/mailbox.json` and copy the code into the
   verification / reset form — the same codes you would have received by
   email.

**Hard guards** (never active outside local dev):

- Disabled by default (`EMAIL_TEST_MODE` must be explicitly `true`).
- Ignored when `APP_ENV`/`ENVIRONMENT` is `production`/`prod`.
- Ignored when real SMTP credentials are configured (`SMTP_USER` +
  `SMTP_PASS`) — real mail is never silently redirected to a file.
- The mailbox stores only recipient, subject, kind, the single-use code and
  its link. It **never** stores passwords, SMTP credentials, or secrets
  (the code is a short-lived single-use token by design).

**Complete human validation workflow (local dev)**

1. `python -m scripts.seed_auth` (roles/permissions + real admin, optional —
   the demo seed does this too).
2. `python -m scripts.seed_demo`.
3. Start the stack: `powershell -ExecutionPolicy Bypass -File scripts/dev_all.ps1`.
4. Verify portals load: client :3000, admin :3001, owner :3002, website :3010,
   API :8000 (`/docs`).
5. Log in as each demo role (creds §1) and confirm the redirect target.
6. Registration/verification test (requires a **running API with
   `EMAIL_TEST_MODE=true`**):
   - Register a throwaway user on the client portal.
   - The API replies "Registration successful. Please verify your email."
   - Read `logs/dev_mailbox/mailbox.json` → copy the `verify_email` code.
   - Enter it in the client portal → login succeeds (redirect
     `/client/dashboard`).
   - Repeat for "Forgot password" → `reset_password` code appears in the
     mailbox.
7. Delete the throwaway user afterwards (it lives only in dev).

## 5. Reset / cleanup

```powershell
# 1. Reset the dev database (destroys ALL dev data, including demo rows)
#    Stop the stack first (stop_all.ps1), then recreate the DB, e.g.:
psql -U postgres -c "DROP DATABASE IF EXISTS ict_funded_ea;"
psql -U postgres -c "CREATE DATABASE ict_funded_ea;"

# 2. Recreate schema + seed everything:
python -m scripts.seed_auth    # roles/permissions + real admin
python -m scripts.seed_demo    # demo kit (idempotent)

# 3. Remove only the demo rows (keep the rest of the dev DB).
#    The seed rows are all linked to the demo users / demo keys below —
#    run these against the dev database (ict_funded_ea):
DELETE FROM paper_trades
 WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'demo.%@ict-ea-demo.dev');
DELETE FROM account_scans WHERE account_id IN
  (SELECT id FROM trading_accounts WHERE user_id IN
    (SELECT id FROM users WHERE email LIKE 'demo.%@ict-ea-demo.dev'));
DELETE FROM risk_profiles WHERE account_id IN
  (SELECT id FROM trading_accounts WHERE user_id IN
    (SELECT id FROM users WHERE email LIKE 'demo.%@ict-ea-demo.dev'));
DELETE FROM trading_accounts WHERE user_id IN
  (SELECT id FROM users WHERE email LIKE 'demo.%@ict-ea-demo.dev');
DELETE FROM licenses WHERE license_key = 'ICT-DEMO-A1B2-C3D4';
DELETE FROM subscriptions WHERE user_id IN
  (SELECT id FROM users WHERE email LIKE 'demo.%@ict-ea-demo.dev');
DELETE FROM support_tickets WHERE ticket_number = 'DEMO-2026-0001';
DELETE FROM news WHERE id IN (SELECT id FROM news WHERE title LIKE 'Welcome to your demo environment%');
DELETE FROM news_events WHERE news_id LIKE 'DEMO-FF-%';
DELETE FROM ea_builds WHERE version = '9.9.9-demo';
DELETE FROM site_settings WHERE key = 'demo.seed_version';
DELETE FROM audit_logs WHERE payload_json->>'synthetic' = 'true'
   OR user_id IN (SELECT id FROM users WHERE email LIKE 'demo.%@ict-ea-demo.dev');
DELETE FROM users WHERE email LIKE 'demo.%@ict-ea-demo.dev';
```

For EMAIL_TEST_MODE cleanup: delete `logs/dev_mailbox/mailbox.json` (or leave
it — it is local-only). Make sure `EMAIL_TEST_MODE` is not set anywhere when
running non-dev environments.

## 6. Security & compliance notes (CLAUDE.md)

- No secrets are hardcoded: demo passwords are documented dev-only
  credentials; no API keys, tokens, or broker credentials are stored.
- The seed never writes to `config/.env` or any production config file.
- Audit logging follows the project conventions (`security/audit.py`); the
  synthetic audit rows are labelled `synthetic: true` in the payload.
- No business logic was added to Telegram handlers or portal routes; the seed
  writes directly through the existing models/repositories.

## 7. QA — scripts/_qa_human_validation.py

```powershell
# dev DB only; requires a running PostgreSQL + the venv
python scripts/_qa_human_validation.py
```

Covers, with PASS/FAIL output and a non-zero exit code on failure:

1. **Idempotent seeding** — runs the seed twice, asserts stable non-zero
   counts and no duplicates.
2. **Owner/admin/client login** — correct role + redirect target for each.
3. **`email_verified` behaviour** — demo users login immediately; a fresh
   unverified user gets a code through the dev mailbox (with
   `EMAIL_TEST_MODE=true`), verifies via `/auth/verify-email/confirm`, then
   logs in.
4. **Isolation** — a client token is rejected (403) by admin endpoints; owner
   and admin tokens are accepted.
5. **Auth + RBAC regression** — roles/permissions still seed, login/refresh
   still works, `password` verification still enforces rules.
6. **No production config changes** — `config/` files are untouched
   (mtime-snapshot comparison) and `EMAIL_TEST_MODE` is not persisted in
   `config/.env`.
