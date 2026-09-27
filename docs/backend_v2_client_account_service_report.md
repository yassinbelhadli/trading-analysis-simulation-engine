# Backend V2 ClientAccountService Module Report

## Status

- Module: client MT4/MT5 account lifecycle
- Status: Complete and verified
- Behavior compatibility: preserved
- Frontend changes: none
- Database schema changes: none
- Trading Engine/runtime implementation changes: none
- Telegram workflows: not changed

## Files Changed

- `api/services/client_account_service.py`
- `api/services/license_service.py`
- `api/routes/client/accounts.py`
- `database/repositories/account_repository.py`
- `database/repositories/license_repository.py`
- `scripts/_qa_backend_v2_account_golden.py`
- `tests/backend_v2_account_golden.json`

## Routes Affected

- `GET /api/client/accounts`
- `POST /api/client/accounts`
- `PATCH /api/client/accounts/{account_id}`
- `DELETE /api/client/accounts/{account_id}`
- `POST /api/client/accounts/{account_id}/disconnect`
- `POST /api/client/accounts/{account_id}/reconnect`

The route paths, methods, response shapes, HTTP statuses, error details, validation order, audit events, engine start/stop ordering, and commit ordering remain compatible.

## Services Introduced or Extended

- Added concrete `ClientAccountService` for list, add, rename, remove, disconnect, and reconnect workflows.
- Reused `LicenseService` for active-license selection and account-limit semantics.
- Kept MT connection calls on the existing `mt_connector` singleton so QA monkeypatches and MT behavior remain unchanged.
- Kept engine calls on the existing `engine_manager` integration without modifying engine code.

## Repository Layer

- Reused the existing `AccountRepository` and `ScanRepository`.
- Reused the existing `LicenseRepository` through `LicenseService`.
- Added `AccountRepository.create_client_account()` to persist the account and its `RiskProfile` aggregate in the existing session.
- Added one ordered license query and limit queries to the existing `LicenseRepository`/`LicenseService` boundary.
- Did not create a `RiskProfileRepository`, generic base repository, interface hierarchy, or new repository file because there is no second genuine consumer or independent domain boundary.

## Compatibility Adapter

`api/routes/client/accounts.py` is now an HTTP-only adapter:

- dependencies and request body remain unchanged;
- service errors map to the previous HTTP status/details;
- the existing JSON response payloads are returned by the service;
- no existing consumer needs a change.

## Golden Master

The account golden master covers:

- list before provisioning;
- add with mocked MT scan;
- list after add;
- duplicate account;
- invalid login;
- rename;
- disconnect;
- reconnect;
- soft removal;
- missing-account removal.

Every step records request, response, status, selected database state before/after, and audit delta.

Result:

```text
License Golden Master: PASS
Account Golden Master: PASS
```

## Regression Results

| Suite | Result |
|---|---|
| `scripts/_qa_client_sprint1.py` | 54/54 PASS |
| `scripts/_qa_client_sprint2.py` | 62/62 PASS |
| `scripts/_qa_auth_full.py` | 22/22 PASS |
| `scripts/_qa_wizard.py` | 13/13 PASS |
| License Golden Master | PASS |
| Account Golden Master | PASS |
| `admin_dashboard`: `npx tsc --noEmit` | PASS |
| `admin_dashboard`: `npm run build` | PASS |

## Remaining Technical Debt

- Admin license/account routes still contain their own persistence/business logic.
- Telegram onboarding still has a separate account/license lifecycle.
- License binding fields remain split between `License.bound_account_id` and `TradingAccount.license_id`.
- Transaction ownership remains unchanged.
- Concurrent account-limit/fingerprint races remain undocumented behavior.
- MT4 bridge write-contract gaps remain untouched.

## Scope Boundary

Sprint 2 did not change:

- dashboard aggregation or caching;
- frontend API clients;
- billing;
- Telegram routes or handlers;
- realtime transport;
- Trading Engine, Detection, Risk, Execution, Simulation, Renderer, MT4, or MT5 implementation.
