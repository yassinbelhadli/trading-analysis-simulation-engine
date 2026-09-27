# Phase 6 — Platform Integrations (Planning ONLY + 6.0 Foundations implemented)

**Status:** AUDIT COMPLETE — planning document. **Phase 6.0 Foundations
implemented and QA-verified** (see §14.1); phases 6.1–6.4 remain planned and
await explicit approval. No provider credentials were connected, no schema
changed, no frozen Backend V2 contract was modified.
**Based on:** full read-only audit of the frozen Backend V2, `telegram_bot/`,
`billing/`, `license_system/`, `owner_portal/`, `admin_dashboard/`,
`client_dashboard/`, `website/`, `database/`, `config/`, `scripts/`, `tests/`.
**Constraint:** this document plans Phase 6. It does NOT implement anything
beyond the approved 6.0 sub-phase.

---

## 0. Purpose, Constraints & Tag Legend

### Purpose
Turn the platform's standalone parts (Website + Client + Admin + Owner) into one
connected system by making Email, Telegram, Billing, Notifications and (later)
Social production-ready. Trading profitability is explicitly **out of scope** —
the platform must be functionally complete before the Trading Engine is tuned.

### Binding constraints (carried from Phase 5)
- No modifications to frozen Backend V2 `/api/admin/*` + `/auth/*` contracts,
  Trading Engine, or DB schema **without a separate approved change**.
- No payment-provider choice is made in this document.
- No DNS/DKIM/DMARC changes, no VPS purchase, no deployment, **no real provider
  credentials connected**.
- Never expose plaintext secrets (OQ-3 extends to all Phase 6 integrations).
- No fake integrations — anything provider-dependent is marked and gated.

### Tag legend
| Tag | Meaning |
| --- | --- |
| `EXISTING` | Shipped and wired (may still need credentials) |
| `PARTIAL` | Exists but incomplete / dead / unwired / not enforced |
| `CONTRACT GAP` | Referenced but missing — must be built or the reference removed |
| `PROVIDER DEPENDENCY` | Requires an external provider / DNS / real credentials |
| `FUTURE WORK` | Nothing exists yet; planned |

---

## 1. Production Email

### 1.1 What exists today — `api/services/email_service.py`

| Item | Tag | Detail |
| --- | --- | --- |
| Central sender `send_email(to, subject, body_text, ...)` | `EXISTING` | stdlib `smtplib`, `SMTP_SSL` or `SMTP`+`STARTTLS`, `login()`, returns `bool`. No Message-ID capture, no persistence. |
| Env config with runtime overrides | `EXISTING` | `SMTP_HOST/PORT/USER/USERNAME/PASS/SECURITY/TIMEOUT/FROM/REPLY_TO` + settings overrides via `site_settings` category `email` (`decrypt_secrets=True`). |
| Auth verify + reset flow | `EXISTING` | `/auth/register`, `/auth/login` (unverified gate), `/auth/verify-email/send|confirm`, `/auth/forgot-password`, `/auth/reset-password`; `VerificationToken` (8-char code, 1h, single-use). |
| Template registry (DB textareas) | `EXISTING` | `email.template_welcome/payment/expiring/expired/reset/license` in `site_settings`. `{placeholder}` → `str.replace`. |
| Secret handling | `EXISTING` | `email.smtp_pass` `is_secret=True`, stored `"enc:"+Fernet`, masked `••••••••` on `GET /settings`; `PUT` returns decrypted (documented boundary — Owner UI deny-list mandatory, already in place). |
| `send_license_activated_email` | `EXISTING` | Wired from `api/routes/admin/licenses.py`. |
| Mocked QA | `EXISTING` | `scripts/_qa_phase2_auth_email.py` (FakeSMTP: STARTTLS/SSL, config-guard, provider-failure diagnostics, links). |

### 1.2 Gaps

| # | Gap | Evidence | Tag |
| --- | --- | --- | --- |
| E1 | Real SMTP never used — `SMTP_PASS` empty in `config/.env`; only mocked sends | email_service.py; `.env` | `PROVIDER DEPENDENCY` |
| E2 | DKIM / DMARC / SPF: **zero code support**; docs list SPF present, `default._domainkey`, `privateemail._domainkey`, `_dmarc` **not resolved** | `docs/infrastructure_activation_report.md:143–146` | `PROVIDER DEPENDENCY` |
| E3 | Unwired senders: `send_welcome_email`, `send_payment_success_email`, `send_subscription_expiring_email`, `send_subscription_expired_email` defined, **never called** | repo-wide grep | `CONTRACT GAP` |
| E4 | Settings schema drift: `email_service` reads `email.smtp_username`, `email.smtp_security`, `email.smtp_timeout_seconds`, `email.smtp_reply_to`, `email.client_portal_url` — **none exist in `SETTINGS_SCHEMA`**; `PUT /settings` would `KeyError` on them | `email_service.py:68–85` vs `site_settings.py:54–83` | `CONTRACT GAP` |
| E5 | No verification-email template key (only reset/license/welcome/payment/expiring/expired) | site_settings.py | `CONTRACT GAP` |
| E6 | Delivery diagnostics log-only (`delivery_id`); no Message-ID, no send timestamp DB record, no attempt/result table | email_service.py:135,184–205 | `FUTURE WORK` |
| E7 | No outbox, retry/backoff, bounce/DSN, suppression list; synchronous `smtplib` blocks the async event loop | email_service.py:165–205 | `FUTURE WORK` |
| E8 | From-address policy fragmented (3 senders: default / `billing_address` / `support_address`); footer typo `support@ictfundedea.com`; envelope `MAIL FROM` not set | email_service.py:107–120 | `PARTIAL` |
| E9 | Emails hardcoded English — CLAUDE.md mandates AR/EN/FR/ES for user messages; `translator.py` unused in email path | email_service.py | `FUTURE WORK` |
| E10 | No SMTP/email component in system health (`health_monitor`, `/api/admin/system-health*`) | core_engine/health; admin_health_service.py | `FUTURE WORK` |
| E11 | Real verification delivery + real password-reset E2E never tested against a real mailbox | — | `PROVIDER DEPENDENCY` |

### 1.3 Production requirements to document (NOT to configure here)
SMTP host/port/security (STARTTLS 587 or SSL 465), dedicated from-addresses
(`no-reply@`, `billing@`, `support@`), DKIM selector keys + DMARC policy + SPF
record, verified sender domains, bounce/return-path mailbox, sending rate limits.

---

## 2. Telegram

### 2.1 What exists today

| Area | Tag | Detail |
| --- | --- | --- |
| Entrypoint | `EXISTING` | `telegram_bot/bot.py` — PTB `ApplicationBuilder.run_polling()`. Long polling only. |
| **Dual entrypoint** | `CONTRACT GAP` | `telegram_bot/api_client.py` builds a second singleton `ApplicationBuilder` (used by `admin/tickets.py` + `test_telegram_demo.py`) → two pollers on one token risk. |
| Commands | `EXISTING` | `/start`, `help`, `license`, `history`, `open_trades`, `performance`, `validation`, `debug_smoke`, `status` (via `commands/*`, `command_handlers.py`). |
| Handlers | `EXISTING` | `handlers/message_handler.py` (state machine), `handlers/callback_handler.py`, 26 callback modules (`account_detail`, `activate_bot`, `enter_license_key`, `mt5`, `pause_resume`, `rescan_account`, `risk_mode`, ...). |
| Onboarding | `EXISTING` | 14-step flow: language → account_type → broker/prop_firm → trading_mode → MT5 warning → terms → platform → server → login → password → confirm (`onboarding.py`, `onboarding_state.py`, `services/setup.py`). |
| Linking + verification | `EXISTING` | `services/license_binding_service.py`, `services/account_verification_service.py`, `services/mt_connector.py` (real MT4/MT5 + mock via `USE_MOCK_TELEGRAM_SCAN`). |
| Trade lifecycle | `EXISTING` | `trading/signal_service.py` (charts via `renderer_bridge.RenderService`), `execution_service.py`, `lifecycle_service.py` (TP/BE), templates `trade_entry/close/be/partial`. |
| Client telegram API | `EXISTING` | `api/routes/client/telegram.py`: GET status, POST connect/disconnect, PATCH preferences, POST test (real `api.telegram.org` unless `TELEGRAM_TEST_MODE`). |
| i18n scaffold | `PARTIAL` | `translator.py` works, but `locales/{en,ar,fr,es}.py` ~10 keys each; most UI strings hardcoded per-handler dicts. |

### 2.2 Gaps

| # | Gap | Evidence | Tag |
| --- | --- | --- | --- |
| T1 | `telegram_bot/alerts.py` imports nonexistent `TelegramBot` / `TelegramResult` — broken legacy file | alerts.py vs bot.py | `CONTRACT GAP` |
| T2 | `api/routes/admin/news.py:201` imports missing `services.telegram_service.broadcast_message`; `except ImportError: pass` swallows → broadcast always sends **0**, `telegram_sent` never set | admin/news.py:201–205 | `CONTRACT GAP` |
| T3 | `AlertService` (20 event types, dedup, charts), `AdminAlertService`, `NewsCountdownService` defined but **never started in production** — notifications offline unless `e2e_test_runner.py` runs | grep | `PARTIAL` |
| T4 | `restart_service()` is a message-only stub — `/system-health/telegram/restart`, `/mt5/restart`, `/api/restart` do nothing | admin_health_service.py:96–97 | `CONTRACT GAP` |
| T5 | `admin_commands.py` empty — no admin/owner commands in bot; `telegram.send` permission has no endpoint; Admin `telegram` page = `ContractGap` placeholder | admin_dashboard/app/dashboard/telegram/page.tsx | `CONTRACT GAP` |
| T6 | `site_settings` `telegram.*` keys (enabled, default_language, welcome_message, main_menu_message, support_message, signal_include_chart) **never read by the bot** | grep | `PARTIAL` |
| T7 | Env contract incomplete: `TELEGRAM_BOT_USERNAME`, `TELEGRAM_TEST_MODE`, `ADMIN_CHAT_ID` used but not in `config/settings.py` | grep | `CONTRACT GAP` |
| T8 | Empty modules (`menus/*`, `screenshots.py`, `subscriptions.py`, `onboarding_flow.py`, `conversation.py`, `account_service.py`, `support_service.py`, `ui/messages.py`) | 0-byte files | `PARTIAL` |
| T9 | Per-user notification prefs (`NOTIF_KEYS`) stored but **not enforced** by `AlertService` (sends to every user with `telegram_id`) | client/telegram.py:24; alert_service.py | `PARTIAL` |
| T10 | Webhook transport absent (long polling only) | grep | `FUTURE WORK` |
| T11 | Weekly/monthly report summaries only invoked from tests | report_service.py | `PARTIAL` |

### 2.3 Provider dependency
Real `TELEGRAM_BOT_TOKEN`, a single bot entrypoint, and (production) a webhook
URL are required. No real token is connected in this phase.

---

## 3. Billing

### 3.1 What exists today

| Item | Tag | Detail |
| --- | --- | --- |
| Product plan catalog | `EXISTING` | `api/services/plans_config.py`: `starter` $29 / `professional` $59 / `premium` $99 / `enterprise` (+ yearly); `PlanDefinition` + `Promotion` tables; admin plans/restore-defaults routes. |
| Entitlement (account limits) | `EXISTING` | `license_system/license_service.py` `get_account_limits`; `client_account_service.add_account` enforces `max_accounts` / `UNLIMITED_PLANS`. **License-based, not subscription-based.** |
| Feature flags | `PARTIAL` | `xauusd`, `nas100`, `telegram_alerts`, ... stored on plans but **no enforcement** found. |
| Client subscription surface | `EXISTING` | `GET /api/client/subscription`, `POST cancel`, `POST renew` (renew = free manual date-extension, **no payment**); admin subscriptions list + cancel. |
| Revenue analytics | `EXISTING` | `/api/admin/analytics/revenue` (admin + owner + billing). |
| Admin/Owner UI | `EXISTING` | Admin plans/subscriptions/payments/revenue/promotions/coupons(placeholder); Owner billing + promotions + revenue pages. |

### 3.2 Gaps

| # | Gap | Evidence | Tag |
| --- | --- | --- | --- |
| B1 | **No `Payment`, `PaymentMethod`, or `Invoice` models.** "Payments" are faked from `AuditLog` rows with `event_type LIKE 'payment.%'` | billing.py; models.py | `CONTRACT GAP` |
| B2 | `billing/{payments,invoices,renewals,refunds}.py`, `api/routes/subscriptions.py`, `license_system/{subscription_manager,plan_manager}.py` — **all empty stubs** | 0-byte files | `CONTRACT GAP` |
| B3 | No subscription→license provisioning: purchase/renewal does not create/extend a `License`; a user can hold a paid subscription and zero licenses | grep | `CONTRACT GAP` |
| B4 | No upgrade/downgrade/proration path; no plan-key normalization — `License.plan` defaults to `"standard"` which is **not** a product plan key (starter/professional/premium/enterprise); "Standard/Pro/Infinite" come from funded-challenge data (`telegram_bot/data/prop_firms.py`) with no mapping layer | models.py; test_db_repositories.py | `CONTRACT GAP` |
| B5 | No failed-payment / dunning / grace / suspension flow; `billing.refund` permission defined but unused | grep | `CONTRACT GAP` |
| B6 | No recurring billing job; `background_runner.py` runs engine only; no APScheduler anywhere | background_runner.py | `CONTRACT GAP` |
| B7 | No payment webhook endpoints, signature verification, or idempotency handling | grep | `PROVIDER DEPENDENCY` |
| B8 | Billing emails (`payment_success`, `expiring`, `expired`) never invoked | email_service.py | `CONTRACT GAP` |
| B9 | Client `billing/page.tsx` is a "Coming soon" placeholder; coupons page placeholder | client_dashboard | `PARTIAL` |
| B10 | No tests for webhook security, idempotency, dunning, provisioning, plan-key validity | tests/ | `CONTRACT GAP` |

### 3.3 Provider policy
**No provider is chosen in this document.** Requirements to evaluate (later, in an
approved billing sub-phase): checkout, recurring billing, webhook events
(payment_succeeded/failed, invoice.updated, subscription.canceled/expired),
idempotency keys, webhook signature verification, refunds, PCI scope (prefer
hosted checkout — no card data in the platform).

---

## 4. Notifications

### 4.1 Existing pipeline pieces

| Stage | Tag | Detail |
| --- | --- | --- |
| Event | `EXISTING` | `core_engine/events/event_types.py` (`EventType`, 45+ types) + in-process `event_bus.EventBus` (pub/sub). **Process-local only.** |
| Producers | `EXISTING` | `engine_runner.py`, `scanner.py`, `news_countdown_service.py` (60/30/15/5/0 min), `api/services/news_broadcast.py` (USD HIGH/MEDIUM, 2h window). |
| Channel | `PARTIAL` | Telegram via `AlertService` (20 events, `DEDUP_COOLDOWN`, charts) — **not started in prod**; `AdminAlertService` dead; `NotificationManager` in-memory print-only. |
| Template | `PARTIAL` | Email: DB textareas; Telegram: hardcoded per-event English strings. |
| Delivery | `PARTIAL` | Direct synchronous sends; no queue/retry/rate-limit/backoff/provider abstraction; admin broadcast broken (T2). |
| Audit | `PARTIAL` | `log_event` rows + boolean flags (`News.telegram_sent`, `NewsEvent.telegram_sent`); no per-recipient delivery log. |
| Preferences | `PARTIAL` | `user.preferences.notifications` JSON (`signals, filled, tp, sl, news, weekly_report, monthly_report`) — **not enforced** by delivery (T9). |

### 4.2 Gaps

| # | Gap | Tag |
| --- | --- | --- |
| N1 | No rule engine — routing hardcoded `if/elif` on event_type; no cross-process transport / outbox | `FUTURE WORK` |
| N2 | No channel abstraction; email is not wired as an event channel; admin channel dead | `FUTURE WORK` |
| N3 | No delivery queue/retry/rate-limit; no `Notification` persistence table; no per-recipient status | `FUTURE WORK` |
| N4 | `emails.read`, `emails.send`, `telegram.send` permissions exist with **no endpoints** | `CONTRACT GAP` |
| N5 | Preferences stored as unstructured JSON, validated ad-hoc | `PARTIAL` |

### 4.3 Target architecture (design for Phase 6)
```
Event  → Rule  → Channel  → Recipient  → Template  → Delivery  → Audit
EventType   match   telegram   user prefs    per-lang     outbox/retry  log_event +
(EventBus)  rules   email      + roles       (AR/EN/FR/ES)  status       delivery log
                    (future: social)
```
Design decisions to confirm at implementation time (NOT now):
- Persisted `Notification` feed vs delivery-only outbox.
- Rule model (per-event-type default + user override).
- Delivery worker in `background_runner.py` (the only scheduler today).
- Channel/recipient resolution order and dedup (reuse `AlertService.DEDUP_COOLDOWN`).

---

## 5–7. Social — Instagram / Facebook / X (GREENFIELD)

| Item | Tag | Detail |
| --- | --- | --- |
| Existing code | `FUTURE WORK` | **Zero** social code, config, dependency or model anywhere (audit: only false positives — `OAuth2PasswordBearer` is FastAPI internal; `og:` metadata is website SEO). |
| Provider APIs required | `PROVIDER DEPENDENCY` | Meta Graph API (Instagram Graph, Facebook Page), X API v2; OAuth 2.0 app credentials; publishing + media-upload + scheduling + webhooks for status. |
| Data model needed | `FUTURE WORK` | `SocialAccount` / OAuth token store (encrypted tokens, scopes, expiry), provider credentials per page/account. |
| Permissions/RBAC | `FUTURE WORK` | New capability surface (owner/admin only); no existing permission. |

Feasibility gate (a later approved sub-phase, before any code):
1. Confirm Meta/X business-account requirements + app review + token scopes.
2. Decide channels (IG Feed, FB Page, X) and media rules.
3. Decide scheduling source of truth (news/announcements pipeline).
No fake integrations — nothing renders until provider OAuth is real.

---

## 8. Integration Status & Health

| Item | Tag | Detail |
| --- | --- | --- |
| System-health surface | `PARTIAL` | `/api/admin/system-health*` reads `heartbeat.json` + `health_report.json`; **no email/telegram/billing component**; `restart_service()` stub (T4). |
| Owner Overview payload | `PARTIAL` | `OverviewEngine` already carries `mt5_connected` + `telegram_connected` but Owner overview/system pages **do not render them** (natural place to add status cards). |
| Admin restart wrappers | `PARTIAL` | `restartTelegram/restartMT5Bridge/restartAPI` wrapped in `admin_dashboard/lib/api.ts:225–230` but called by **no page**; backend is a stub. |
| Client telegram card | `EXISTING` | Client overview renders `telegram_connected` dot. |

Required (FUTURE WORK): a real component registry in system health for
`email` (SMTP ping), `telegram` (bot getMe), `billing` (provider API health),
`news`, `engine`; real restart actions or removal of the stub contract.

---

## 9. Event → Rule → Channel → Template → Delivery → Audit (summary)

| Stage | Today | Phase 6 target |
| --- | --- | --- |
| Event | `EXISTING` in-process EventBus | keep; add cross-process outbox if needed |
| Rule | `FUTURE WORK` (hardcoded routing; prefs unenforced) | rule resolution (defaults + user prefs) |
| Channel | `PARTIAL` Telegram client; admin dead; email sink | unified channel registry |
| Template | `PARTIAL` email DB textareas; telegram hardcoded | per-channel, i18n (AR/EN/FR/ES) |
| Delivery | `PARTIAL` synchronous; no retry | outbox + retry/backoff + provider abstraction |
| Audit | `PARTIAL` log_event + boolean flags | persisted delivery log, per-recipient status |

---

## 10. Security & Secret Boundaries

### 10.1 Credential inventory (names only — values live in env, encrypted in DB)
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ADMIN_CHAT_ID`, `TELEGRAM_BOT_USERNAME`,
`SMTP_HOST/PORT/USER/PASS/SECURITY/TIMEOUT/FROM/REPLY_TO`, `SUPPORT_EMAIL`,
`BILLING_EMAIL`, `FRONTEND_URL`, `CLIENT_PORTAL_URL`, `API_PUBLIC_URL`,
`HOOKS_PUBLIC_URL`, `ENCRYPTION_KEY`, `JWT_SECRET`, `DATABASE_URL`,
`ADMIN_TOKEN`, MT5/MT4 creds, `NEWS_PROVIDER`. Payment-provider + social OAuth
credentials are **net-new** (Phase 6 adds them, Phase 6.4 OAuth).

### 10.2 Rules to carry into implementation
- Secrets via env (`config/.env`) or `site_settings` with `is_secret=True` +
  Fernet `enc:` (existing pattern: `email.smtp_pass`).
- `GET /settings` masks; Owner/Admin UIs never write secrets (Owner deny-list
  exists; **Admin `settings/page.tsx` currently sends masked-secret fields back
  without a deny-list sanitizer — must be fixed with the email phase**).
- Payment webhooks: signature verification + idempotency; sanitize payloads
  before logging; never log tokens/passwords.
- OAuth tokens (social): encrypted at rest, scoped, refreshable, revocable.
- Webhook secret + provider API keys stored encrypted, never in frontend.

---

## 11. Owner Control Plane Mapping

| Integration | Existing Owner surface | Phase 6 work |
| --- | --- | --- |
| Email | `settings/page.tsx` Email category (SMTP host/port/from/templates; `smtp_pass` read-only masked) | add delivery-status card; add health component |
| Telegram | none (nav has no Telegram item) | new **Control Plane → Telegram** status card (bot health, connected clients, broadcast); new `Marketing → Broadcast` wiring (currently dead) |
| Billing | `billing/page.tsx` (plans/subscriptions/payments), `revenue/page.tsx`, `promotions/page.tsx` | real payment rows, invoice list, dunning/refund status |
| Notifications | none | new status card: channels healthy, deliveries/failures |
| Social | none (Marketing group) | new `Marketing → Social` (gated by provider phase) |

## 12. Client Portal Mapping

| Integration | Existing Client surface | Phase 6 work |
| --- | --- | --- |
| Email | verify/reset pages (backend-driven) | real delivery; i18n emails |
| Telegram | `dashboard/telegram/page.tsx` read-only (disabled test button); `/api/client/telegram/{connect,disconnect,preferences,test}` **already frozen but unwired** | wire connect/disconnect/test; enforce prefs |
| Billing | `dashboard/subscription/page.tsx` (cancel/renew), `dashboard/billing/page.tsx` (placeholder) | real checkout, payment methods, invoices |
| Notifications | `dashboard/notifications/page.tsx` (toggles saved to `user.preferences`) | make toggles actually gate delivery (T9) |

## 13. Data Model Gaps (net-new tables — no schema change without approval)

| Table | Purpose |
| --- | --- |
| `Payment` | real payment history (user, plan, amount, currency, provider, provider_ref, status, paid_at) |
| `Invoice` | invoice numbering, totals, PDF reference |
| `EmailDelivery` | email outbox/log: to, subject, template, status, attempts, provider_msg_id, error, sent_at |
| `NotificationPreference` | structured prefs (replace/augment JSON blob) |
| `NotificationRule` / `NotificationChannel` / persisted feed | rule → channel → delivery + audit |
| `TelegramBinding` uniqueness | one chat ↔ one user/license (today split across `users.telegram_id` unique + `licenses.telegram_id` non-unique) |
| `SocialAccount` / OAuth token store | social OAuth (Phase 6.4) |

Migration note: repo uses Alembic (15 versions) **plus** ad-hoc `Base.metadata.create_all` in `api/main.py` and QA suites — two schema paths; a migration strategy decision is required before adding tables.

---

## 14. Phased Implementation Order (proposal — awaits approval)

| Phase | Scope | Depends on | Provider gate |
| --- | --- | --- | --- |
| **6.0 Foundations** ✅ implemented | Notification pipeline skeleton (rule/channel/template/delivery + persisted delivery log), system-health integration + honest restart status, single Telegram entrypoint, perms→endpoints for `emails.*`/`telegram.send` | none | none |
| **6.1 Email Production** | fix E3/E4/E5 schema drift + wire unused senders + `EmailDelivery` + async sender + health component; verification/reset E2E | 6.0 | SMTP creds + DKIM/DMARC/SPF records (owner ops, real DNS) |
| **6.2 Telegram Production** | fix T1/T2 (broken imports, real broadcast), start `AlertService`/`AdminAlertService`/`NewsCountdownService` in `background_runner.py`, wire `telegram.*` settings + env contract, admin/owner controls, enforce prefs (T9), webhook transport | 6.0 | real bot token + webhook URL |
| **6.3 Billing** | `Payment`/`Invoice` models + migration, checkout, webhook + idempotency, subscription→license provisioning, recurring/dunning job, upgrade/downgrade, plan-key normalization, wire billing emails | 6.0, 6.1 | payment provider selection (separate approval) |
| **6.4 Social** | feasibility gate → provider selection → OAuth + token store → publishing/scheduling → status/error handling | 6.0 | Meta/X app approval + tokens |

Ordering rationale: 6.0 builds the shared delivery backbone; 6.1/6.2 are
credential-gated; 6.3 depends on email for dunning notices; 6.4 is fully gated
on external provider approval. Each phase ships **with its own QA** and never
touches the Trading Engine or frozen contracts.

### 14.1 6.0 Foundations — implemented

Approved and shipped. Deliverables:

- **Notification pipeline skeleton** (`api/services/notifications/`):
  `preferences.py` (canonical `NOTIF_KEYS`/`DEFAULT_NOTIFICATIONS`, merged
  user overrides), `rules.py` (`resolve_channels`: per-event defaults + user
  preference gates), `messages.py` (EN/AR/FR/ES), `templates.py`
  (`render_telegram`/`render_email_subject`/`render_email_body`),
  `channels.py` (`TelegramChannel`/`EmailChannel`/`AuditChannel` + registry,
  all sends gated by `TELEGRAM_TEST_MODE`/`EMAIL_TEST_MODE`),
  `dispatcher.py` (`NotificationDispatcher` with persisted per-recipient
  delivery record in `audit_logs`). No real provider traffic.
- **System-health integrations + honest restart**
  (`api/services/admin_health_service.py`, `api/routes/admin/system_health.py`):
  `GET /api/admin/system-health/integrations` component registry
  (email/telegram/billing/news/engine; no secrets); `POST .../restart` now
  truthfully returns `supported: false` (no process manager) while auditing.
- **Single Telegram entrypoint** (`telegram_bot/app.py`): shared
  `build_application()` factory + `register_handlers`; `bot.py` and
  `api_client.py` both delegate to it — the dual-poller gap (T2/T3 in §2.2)
  is removed.
- **Perms → endpoints** (`api/routes/admin/notifications.py`, registered in
  `admin/bundle.py`): `GET/POST /api/admin/emails/{status,test}` and
  `/api/admin/telegram/{status,test}` enforcing `emails.read`, `emails.send`,
  `telegram.send`; all sends mock-gated and audited (`email.test`,
  `telegram.test`).
- `config/settings.py` env contract completed (`TELEGRAM_BOT_USERNAME` /
  `BOT_USERNAME`).

QA: `scripts/_qa_notifications.py` **49/49 PASS**; full frozen guard rerun
green (Owner 110, Admin 92, Client 53, Auth 22, Sprint1 54, Sprint2 62,
Wizard 13, Golden Masters ×4, Phase2 email, `test_permissions` 7/7).
QA-script maintenance performed to match the refactor:
`scripts/_qa_wizard.py` AU-001 now audits the shared factory in
`telegram_bot/app.py`; `tests/test_permissions.py` expected set synced to the
real `Permission` enum (`tickets.*`, `trades.view`).

Remaining in Phase 6 (still planned, gated, not started): 6.1 Email
Production, 6.2 Telegram Production, 6.3 Billing, 6.4 Social.

## 15. QA Strategy (per phase, layered on the existing regression set)

- Every phase: rerun the frozen guard — Owner 110, Admin 92, Client 53, Auth 22,
  Sprint1 54, Sprint2 62, Wizard 13, Golden Masters (4), Phase2 email, `test_permissions` 7/7.
- **6.0**: new `_qa_notifications.py` — rule resolution, channel registry,
  delivery log rows, dedup, prefs enforcement, health components.
- **6.1**: extend `_qa_phase2_auth_email.py` with async-sender + outbox/retry
  assertions (still FakeSMTP/mocked); real-delivery is a **manual staged
  checklist** (SMTP creds + DNS in place) — never automated against live mail.
- **6.2**: extend `_qa_wizard.py` — alert dispatch, fill/TP/SL/close messages,
  broadcast real path, admin/owner telegram status, single-entrypoint check.
- **6.3**: new `_qa_billing.py` — webhook signature + idempotency, provisioning,
  dunning/grace state machine, proration, plan-key validity, refund (mocked
  provider adapter).
- **6.4**: provider-gated; smoke tests with sandbox accounts only.
- Every provider call behind an interface with a **mock adapter** so CI never
  touches real providers (existing pattern: `USE_MOCK_TELEGRAM_SCAN`,
  `TELEGRAM_TEST_MODE`, FakeSMTP).

## 16. Out of Scope (Phase 6 as planned here)

Trading profitability/tuning, Trading Engine changes, VPS/deployment/DNS
execution, real provider credentials, payment-provider selection, DNS/DKIM
changes, legacy `/admin/*` cleanup, i18n of legacy surfaces beyond the
notification/email pipeline, any database schema change before a migration
strategy decision.

---

**STOP — this is a planning document for phases 6.1–6.4.** The approved
6.0 Foundations sub-phase IS implemented and QA-verified (§14.1). Nothing
beyond 6.0 has been implemented; phases 6.1–6.4 require explicit approval,
provider credentials/DNS, and (6.3) a payment-provider decision before any
code, config, or credential changes.
