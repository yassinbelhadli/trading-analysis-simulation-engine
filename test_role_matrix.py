"""REQ 16 — Backend role enforcement matrix.

Verifies that every admin surface enforces the correct role gate:

  owner  -> unrestricted (200 on everything)
  admin  -> admin surfaces 200, owner-only surfaces 403
  client -> every /api/admin/* surface 403

Gates under test:
  - require_role("owner")   : /roles, /permissions, /trading/*, /analytics/revenue
  - get_current_admin_user  : /plans, /promotions, /subscriptions (admin+)
  - require_permission(...) : /clients, /coupons, /licenses, /ea-builds, /news,
                              /overview, /audit-logs, /system-health, /tickets,
                              /settings, /payment-configs, /emails, /telegram
"""
import httpx
import sys
import time

BASE = "http://localhost:8000"
_T = 30.0
TS = int(time.time()) % 100000

ACCOUNTS = {
    "owner": ("demo.owner@ict-ea-demo.dev", "OwnerDemo!2026"),
    "admin": ("demo.admin@ict-ea-demo.dev", "AdminDemo!2026"),
    "client": ("demo.client@ict-ea-demo.dev", "ClientDemo!2026"),
}

# (label, method, path, expected_status_by_role)
# 200 = allowed, 403 = denied
MATRIX: list[tuple[str, str, str, dict[str, int]]] = [
    # ---- Owner-only surfaces (require_role("owner")) ----
    ("roles list", "GET", "/api/admin/roles", {"owner": 200, "admin": 403, "client": 403}),
    ("permissions list", "GET", "/api/admin/permissions", {"owner": 200, "admin": 403, "client": 403}),
    ("trading overview", "GET", "/api/admin/trading/overview", {"owner": 200, "admin": 403, "client": 403}),
    ("trading active trades", "GET", "/api/admin/trading/active-trades", {"owner": 200, "admin": 403, "client": 403}),
    ("trading signals", "GET", "/api/admin/trading/signals", {"owner": 200, "admin": 403, "client": 403}),
    ("trading risk", "GET", "/api/admin/trading/risk", {"owner": 200, "admin": 403, "client": 403}),
    ("trading engine", "GET", "/api/admin/trading/engine", {"owner": 200, "admin": 403, "client": 403}),
    ("revenue analytics", "GET", "/api/admin/analytics/revenue", {"owner": 200, "admin": 403, "client": 403}),

    # ---- Admin+ surfaces (get_current_admin_user) ----
    ("plans list", "GET", "/api/admin/plans", {"owner": 200, "admin": 200, "client": 403}),
    ("promotions list", "GET", "/api/admin/promotions", {"owner": 200, "admin": 200, "client": 403}),
    ("subscriptions list", "GET", "/api/admin/subscriptions", {"owner": 200, "admin": 200, "client": 403}),
    ("payments list", "GET", "/api/admin/payments", {"owner": 200, "admin": 200, "client": 403}),

    # ---- Permission-gated surfaces (require_permission) ----
    ("clients list", "GET", "/api/admin/clients", {"owner": 200, "admin": 200, "client": 403}),
    ("coupons list", "GET", "/api/admin/coupons", {"owner": 200, "admin": 200, "client": 403}),
    ("licenses list", "GET", "/api/admin/licenses", {"owner": 200, "admin": 200, "client": 403}),
    ("ea-builds list", "GET", "/api/admin/ea-builds", {"owner": 200, "admin": 200, "client": 403}),
    ("news list", "GET", "/api/admin/news", {"owner": 200, "admin": 200, "client": 403}),
    ("overview", "GET", "/api/admin/overview", {"owner": 200, "admin": 200, "client": 403}),
    ("audit logs", "GET", "/api/admin/audit-logs", {"owner": 200, "admin": 200, "client": 403}),
    ("system health", "GET", "/api/admin/system-health", {"owner": 200, "admin": 200, "client": 403}),
    ("tickets list", "GET", "/api/admin/tickets", {"owner": 200, "admin": 200, "client": 403}),
    ("settings", "GET", "/api/admin/settings", {"owner": 200, "admin": 200, "client": 403}),
    ("payment-configs", "GET", "/api/admin/payment-configs", {"owner": 200, "admin": 200, "client": 403}),
    ("emails status", "GET", "/api/admin/emails/status", {"owner": 200, "admin": 200, "client": 403}),
    ("telegram status", "GET", "/api/admin/telegram/status", {"owner": 200, "admin": 200, "client": 403}),
]


# ---- Write (mutation) operations: POST / PUT / DELETE ----
# For role-gate testing we send minimal/invalid payloads. The role gate is
# enforced BEFORE payload validation, so an authorized role may return
# 200/201/400/422 (anything except 403), while an unauthorized role must get 403.
# expected: {role: "allow" | "deny"}
MUTATION_MATRIX: list[tuple[str, str, str, dict, dict[str, str]]] = [
    # ---- Owner-only write surfaces (require_role("owner")) ----
    ("create role", "POST", "/api/admin/roles", {"name": "T3-test-role"}, {"owner": "allow", "admin": "deny", "client": "deny"}),
    ("delete role", "DELETE", "/api/admin/roles/nonexistent-role-id", {}, {"owner": "allow", "admin": "deny", "client": "deny"}),
    ("trading emergency-stop", "POST", "/api/admin/trading/control/emergency-stop", {}, {"owner": "allow", "admin": "deny", "client": "deny"}),
    ("trading disable", "POST", "/api/admin/trading/control/disable", {}, {"owner": "allow", "admin": "deny", "client": "deny"}),

    # ---- Admin+ write surfaces (get_current_admin_user) ----
    ("create plan", "POST", "/api/admin/plans", {"name": "T3-plan"}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("delete plan", "DELETE", "/api/admin/plans/nonexistent-plan", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("create promotion", "POST", "/api/admin/promotions", {"code": "T3PROMO"}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("create subscription", "POST", "/api/admin/subscriptions/create", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),

    # ---- Permission-gated write surfaces (require_permission) ----
    ("create coupon", "POST", "/api/admin/coupons", {"code": "T3COUPON"}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("delete coupon", "DELETE", "/api/admin/coupons/nonexistent-coupon", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("create license", "POST", "/api/admin/licenses", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("delete license", "DELETE", "/api/admin/licenses/nonexistent-license", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("create ea-build", "POST", "/api/admin/ea-builds", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("delete ea-build", "DELETE", "/api/admin/ea-builds/nonexistent-build", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("create news", "POST", "/api/admin/news", {"title": "T3"}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("delete news", "DELETE", "/api/admin/news/nonexistent-news", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("create payment-config", "POST", "/api/admin/payment-configs", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("delete payment-config", "DELETE", "/api/admin/payment-configs/nonexistent-method", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("create user", "POST", "/api/admin/users", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("delete user", "DELETE", "/api/admin/users/nonexistent-user", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
    ("update settings", "PUT", "/api/admin/settings", {}, {"owner": "allow", "admin": "allow", "client": "deny"}),
]


def login(email: str, password: str) -> str:
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=_T)
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    print("=" * 70)
    print("REQ 16 — BACKEND ROLE ENFORCEMENT MATRIX")
    print("=" * 70)

    tokens = {}
    for role, (email, pw) in ACCOUNTS.items():
        try:
            tokens[role] = login(email, pw)
            print(f"  login {role}: OK")
        except Exception as exc:
            print(f"  login {role}: FAILED ({exc})")
            return 1

    headers = {role: {"Authorization": f"Bearer {tok}"} for role, tok in tokens.items()}

    passed = 0
    failed = 0
    failures: list[str] = []

    for label, method, path, expected in MATRIX:
        for role, want in expected.items():
            r = httpx.request(method, f"{BASE}{path}", headers=headers[role], timeout=30)
            got = r.status_code
            ok = got == want
            if ok:
                passed += 1
            else:
                failed += 1
                failures.append(f"{label} [{role}] {method} {path}: expected {want}, got {got}")
                print(f"  FAIL: {label} [{role}] {method} {path} -> {got} (want {want})")

    print(f"\nMatrix: {passed} passed, {failed} failed")

    # ---- Client must never reach ANY admin surface ----
    print("\n--- Client isolation sweep (every admin route must be 403) ---")
    client_ok = 0
    client_fail = 0
    for label, method, path, _ in MATRIX:
        r = httpx.request(method, f"{BASE}{path}", headers=headers["client"], timeout=30)
        if r.status_code == 403:
            client_ok += 1
        else:
            client_fail += 1
            failures.append(f"client isolation: {method} {path} -> {r.status_code} (want 403)")
            print(f"  FAIL: client {method} {path} -> {r.status_code} (want 403)")
    print(f"Client isolation: {client_ok} blocked, {client_fail} leaked")

    # ---- Admin must never reach owner-only surfaces ----
    print("\n--- Admin isolation sweep (owner-only routes must be 403) ---")
    admin_ok = 0
    admin_fail = 0
    owner_only = [m for m in MATRIX if m[3]["admin"] == 403]
    for label, method, path, _ in owner_only:
        r = httpx.request(method, f"{BASE}{path}", headers=headers["admin"], timeout=30)
        if r.status_code == 403:
            admin_ok += 1
        else:
            admin_fail += 1
            failures.append(f"admin isolation: {method} {path} -> {r.status_code} (want 403)")
            print(f"  FAIL: admin {method} {path} -> {r.status_code} (want 403)")
    print(f"Admin isolation: {admin_ok} blocked, {admin_fail} leaked")

    # ---- Write (mutation) operations role-gate sweep ----
    print("\n--- Write operations (POST/PUT/DELETE) role-gate sweep ---")
    mut_ok = 0
    mut_fail = 0
    for label, method, path, payload, expected in MUTATION_MATRIX:
        for role, want in expected.items():
            r = httpx.request(method, f"{BASE}{path}", headers=headers[role],
                              json=payload if payload else None, timeout=30)
            got = r.status_code
            if want == "deny":
                ok = got == 403
            else:
                # Authorized role must NOT be 403 (may be 200/201/400/422/404)
                ok = got != 403
            if ok:
                mut_ok += 1
            else:
                mut_fail += 1
                failures.append(f"mutation {label} [{role}] {method} {path}: want {want}, got {got}")
                print(f"  FAIL: mutation {label} [{role}] {method} {path} -> {got} (want {want})")
    print(f"Write operations: {mut_ok} passed, {mut_fail} failed")

    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")

    total_ok = passed + client_ok + admin_ok + mut_ok
    total_fail = failed + client_fail + admin_fail + mut_fail
    print(f"\n=== ROLE MATRIX: {total_ok} passed, {total_fail} failed ===")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())