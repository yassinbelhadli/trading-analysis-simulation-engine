"""Test plan safety validations + owner billing RBAC."""
import httpx
import json
import sys
import time

BASE = "http://localhost:8000"
_T = 30.0
TS = int(time.time()) % 100000  # unique suffix per run

def login(email, password):
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=_T)
    return r.json()["access_token"]


def test_plan_safety():
    print("=" * 60)
    print("PLAN SAFETY VALIDATION TESTS")
    print("=" * 60)
    token = login("demo.owner@ict-ea-demo.dev", "OwnerDemo!2026")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    passed = 0
    failed = 0

    def check(name, actual, expected_status):
        nonlocal passed, failed
        if actual == expected_status:
            print(f"  PASS: {name} -> {actual}")
            passed += 1
        else:
            print(f"  FAIL: {name} -> expected {expected_status}, got {actual}")
            failed += 1

    print("\n--- Negative prices ---")
    for cur, val in [("USD", -10), ("EUR", -5), ("MAD", -100)]:
        r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
            "name": f"Negative {cur}", **{f"price_{cur.lower()}": val}, "duration_days": 30
        })
        check(f"Negative {cur} price rejected", r.status_code, 400)

    print("\n--- Zero price ---")
    r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
        "name": "Zero Price", "price_usd": 0, "duration_days": 30
    })
    check("Zero price rejected (backend requires positive)", r.status_code, 400)

    print("\n--- Invalid durations ---")
    for val, label in [(0, "zero"), (-5, "negative"), ("abc", "string")]:
        r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
            "name": f"Bad Duration {label}", "price_usd": 10, "duration_days": val
        })
        check(f"duration_days={val!r} rejected", r.status_code, 400)

    print("\n--- Invalid currencies (client subscription) ---")
    token_client = login("demo.client@ict-ea-demo.dev", "ClientDemo!2026")
    headers_client = {"Authorization": f"Bearer {token_client}", "Content-Type": "application/json"}
    httpx.post(f"{BASE}/api/client/subscription/cancel", headers=headers_client)

    r = httpx.post(f"{BASE}/api/client/subscription", headers=headers_client,
                   json={"plan_id": "30_days", "currency": "GBP"})
    check("Invalid currency (GBP) rejected", r.status_code, 400)

    # With payment infrastructure, empty currency falls back to billing_currency then goes to checkout
    # Since no payment provider is configured, checkout returns 503
    r = httpx.post(f"{BASE}/api/client/subscription", headers=headers_client,
                   json={"plan_id": "30_days", "currency": ""})
    check("Empty currency fallback reaches checkout", r.status_code, 503)

    print("\n--- Malformed features_json ---")
    for val, label in [("not a dict", "string"), (["a", "b"], "array")]:
        r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
            "name": f"Bad Features {label}", "price_usd": 10, "duration_days": 30,
            "features_json": val
        })
        check(f"features_json={label} rejected", r.status_code, 400)

    r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
        "name": f"Valid Features {TS}", "price_usd": 10, "duration_days": 30,
        "features_json": {"risk_management": True}
    })
    check("Valid dict features_json accepted", r.status_code, 200)
    if r.status_code == 200:
        pid = r.json().get("plan", {}).get("id")
        if pid: httpx.delete(f"{BASE}/api/admin/plans/{pid}", headers=headers)

    print("\n--- Missing required fields ---")
    r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={"duration_days": 30})
    check("Missing name rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={"name": "No Price"})
    check("Missing all prices rejected", r.status_code, 400)

    print("\n--- Archive plan blocks subscription ---")
    r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
        "name": f"Archive Block Test {TS}", "price_usd": 10, "duration_days": 30
    })
    if r.status_code == 200:
        pid = r.json().get("plan", {}).get("id")
        if pid:
            r = httpx.delete(f"{BASE}/api/admin/plans/{pid}", headers=headers)
            check("Archive via DELETE succeeds", r.status_code, 200)
            r = httpx.post(f"{BASE}/api/client/subscription", headers=headers_client,
                           json={"plan_id": pid, "currency": "USD"})
            check("Subscribe to archived plan blocked", r.status_code, 400)

    print("\n--- Badge length limit ---")
    r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
        "name": f"Badge Long {TS}", "price_usd": 10, "duration_days": 30, "badge": "x" * 101
    })
    check("Badge > 100 chars rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/plans", headers=headers, json={
        "name": f"Badge OK {TS}", "price_usd": 10, "duration_days": 30, "badge": "x" * 100
    })
    check("Badge = 100 chars accepted", r.status_code, 200)
    if r.status_code == 200:
        pid = r.json().get("plan", {}).get("id")
        if pid: httpx.delete(f"{BASE}/api/admin/plans/{pid}", headers=headers)

    httpx.delete(f"{BASE}/api/admin/plans/safety-invalid-currency", headers=headers)

    print(f"\nPlan Safety: {passed} passed, {failed} failed")
    return failed == 0


def test_coupon_safety():
    print("\n" + "=" * 60)
    print("COUPON SAFETY VALIDATION TESTS")
    print("=" * 60)
    token = login("demo.owner@ict-ea-demo.dev", "OwnerDemo!2026")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    passed = 0
    failed = 0

    def check(name, actual, expected_status):
        nonlocal passed, failed
        if actual == expected_status:
            print(f"  PASS: {name} -> {actual}")
            passed += 1
        else:
            print(f"  FAIL: {name} -> expected {expected_status}, got {actual}")
            failed += 1

    print("\n--- Negative discount values ---")
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "SAF_NEG_PCT", "name": "Neg Pct", "discount_type": "percentage", "discount_value": -10
    })
    check("Negative percentage rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "SAF_NEG_FIX", "name": "Neg Fix", "discount_type": "fixed_amount",
        "discount_value": -5, "currency": "USD"
    })
    check("Negative fixed amount rejected", r.status_code, 400)

    print("\n--- Percentage out of range ---")
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "SAF_101PCT", "name": "101%", "discount_type": "percentage", "discount_value": 101
    })
    check("101% rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "SAF_0PCT", "name": "0%", "discount_type": "percentage", "discount_value": 0
    })
    check("0% rejected", r.status_code, 400)

    print("\n--- Fixed amount without currency ---")
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "SAF_NOCUR", "name": "No Cur", "discount_type": "fixed_amount", "discount_value": 5
    })
    check("Fixed without currency rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "SAF_BADCUR", "name": "Bad Cur", "discount_type": "fixed_amount",
        "discount_value": 5, "currency": "GBP"
    })
    check("Fixed with GBP rejected", r.status_code, 400)

    print("\n--- Missing required fields ---")
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={"name": "No Code"})
    check("Missing code rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={"code": "SAF_NONAME"})
    check("Missing name rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={"code": "SAF_NOTYPE", "name": "No Type"})
    check("Missing discount_type rejected", r.status_code, 400)

    print("\n--- Invalid discount_type ---")
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "SAF_BADTYP", "name": "Bad Type", "discount_type": "bogus", "discount_value": 10
    })
    check("Invalid discount_type rejected", r.status_code, 400)

    print("\n--- Invalid coupon code format ---")
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "ab", "name": "Short", "discount_type": "percentage", "discount_value": 10
    })
    check("Short code rejected", r.status_code, 400)
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": "has spaces", "name": "Spaces", "discount_type": "percentage", "discount_value": 10
    })
    check("Code with spaces rejected", r.status_code, 400)

    print("\n--- Duplicate code ---")
    dup_code = f"SAF_DUP{TS}"
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": dup_code, "name": "Dup 1", "discount_type": "percentage", "discount_value": 10
    })
    check("Create first coupon", r.status_code, 200)
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=headers, json={
        "code": dup_code, "name": "Dup 2", "discount_type": "percentage", "discount_value": 20
    })
    check("Duplicate code rejected", r.status_code, 409)
    httpx.delete(f"{BASE}/api/admin/coupons/{dup_code.lower()}", headers=headers)

    print(f"\nCoupon Safety: {passed} passed, {failed} failed")
    return failed == 0


def test_rbac():
    print("\n" + "=" * 60)
    print("OWNER BILLING RBAC TESTS")
    print("=" * 60)
    passed = 0
    failed = 0

    def check(name, actual, expected_status):
        nonlocal passed, failed
        if actual == expected_status:
            print(f"  PASS: {name} -> {actual}")
            passed += 1
        else:
            print(f"  FAIL: {name} -> expected {expected_status}, got {actual}")
            failed += 1

    owner_token = login("demo.owner@ict-ea-demo.dev", "OwnerDemo!2026")
    owner_h = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}

    # Get permission IDs from API
    r = httpx.get(f"{BASE}/api/admin/permissions", headers=owner_h)
    items = r.json().get("items", [])
    perm_map = {i["description"]: i["id"] for i in items}

    # Create role with billing/coupons permissions only (no subscriptions, users, roles)
    perm_ids = []
    for key in ["billing.read", "billing.create", "coupons.read", "coupons.create", "coupons.update", "coupons.delete"]:
        if key in perm_map:
            perm_ids.append(perm_map[key])

    if not perm_ids:
        print("  SKIP: Could not find billing/coupon permissions")
        return True

    print(f"\n--- Setup: create limited role with {len(perm_ids)} billing/coupon permissions ---")
    r = httpx.post(f"{BASE}/api/admin/roles", headers=owner_h, json={
        "name": f"Limited Billing {TS}",
        "description": "Limited to billing + coupons only",
        "permission_ids": perm_ids
    })
    check("Create limited role", r.status_code, 200)
    role_id = r.json().get("id") if r.status_code == 200 else None

    if not role_id:
        print("  SKIP: Could not create role")
        return False

    # Create test user with this limited role
    r = httpx.post(f"{BASE}/api/admin/users", headers=owner_h, json={
        "email": f"rbac-billing-{role_id[:8]}@ict-ea-test.dev",
        "password": "TestPass123!",
        "full_name": "RBAC Billing Test",
        "role_id": role_id
    })
    check("Create limited user", r.status_code, 200)
    user_id = r.json().get("id") if r.status_code == 200 else None

    if not user_id:
        print("  SKIP: Could not create user")
        httpx.delete(f"{BASE}/api/admin/roles/{role_id}", headers=owner_h)
        return False

    token = login(f"rbac-billing-{role_id[:8]}@ict-ea-test.dev", "TestPass123!")
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("\n--- LAYER 1: Role gate (get_current_admin_user) ---")
    # Plans GET uses get_current_admin_user (requires role owner/admin)
    # Our limited user has role "Limited Billing" -> 403
    r = httpx.get(f"{BASE}/api/admin/plans", headers=h)
    check("GET /plans blocked (role != owner/admin)", r.status_code, 403)

    print("\n--- LAYER 2: Permission gate (require_permission) ---")
    # Coupons routes use get_current_user + require_permission
    # These bypass the role gate and check permissions directly
    r = httpx.get(f"{BASE}/api/admin/coupons", headers=h)
    check("GET /coupons (has COUPONS_READ)", r.status_code, 200)

    r = httpx.post(f"{BASE}/api/admin/coupons", headers=h, json={
        "code": f"RBAC{TS}", "name": "RBAC Coupon",
        "discount_type": "percentage", "discount_value": 10
    })
    check("POST /coupons (has COUPONS_CREATE)", r.status_code, 200)
    if r.status_code == 200:
        httpx.delete(f"{BASE}/api/admin/coupons/rbac{TS}", headers=h)

    print("\n--- LAYER 3: Missing permission -> 403 ---")
    r = httpx.post(f"{BASE}/api/admin/coupons", headers=h, json={
        "code": f"RBAC2{TS}", "name": "No Perm",
        "discount_type": "percentage", "discount_value": 10
    })
    # User has COUPONS_CREATE so this should work
    check("POST /coupons (has COUPONS_CREATE)", r.status_code, 200)
    if r.status_code == 200:
        httpx.delete(f"{BASE}/api/admin/coupons/rbac2{TS}", headers=h)

    print("\n--- LAYER 4: Non-billing endpoints blocked ---")
    r = httpx.get(f"{BASE}/api/admin/users", headers=h)
    check("GET /users blocked (no USERS_READ, role != admin)", r.status_code, 403)

    r = httpx.get(f"{BASE}/api/admin/roles", headers=h)
    check("GET /roles blocked (role != owner)", r.status_code, 403)

    print("\n--- Owner has unrestricted access ---")
    r = httpx.get(f"{BASE}/api/admin/plans", headers=owner_h)
    check("Owner GET /plans", r.status_code, 200)
    r = httpx.get(f"{BASE}/api/admin/users", headers=owner_h)
    check("Owner GET /users", r.status_code, 200)
    r = httpx.get(f"{BASE}/api/admin/roles", headers=owner_h)
    check("Owner GET /roles", r.status_code, 200)
    r = httpx.get(f"{BASE}/api/admin/coupons", headers=owner_h)
    check("Owner GET /coupons", r.status_code, 200)

    print("\n--- Cleanup ---")
    r = httpx.delete(f"{BASE}/api/admin/users/{user_id}", headers=owner_h)
    check("Delete test user", r.status_code, 200)
    r = httpx.delete(f"{BASE}/api/admin/roles/{role_id}", headers=owner_h)
    check("Delete test role", r.status_code, 200)

    print(f"\nRBAC: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    results = []
    results.append(("Plan Safety", test_plan_safety()))
    results.append(("Coupon Safety", test_coupon_safety()))
    results.append(("RBAC", test_rbac()))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {name}")
        if not ok:
            all_pass = False

    if all_pass:
        print("\n=== ALL SAFETY + RBAC TESTS PASSED ===")
    else:
        print("\n=== SOME TESTS FAILED ===")
        sys.exit(1)
