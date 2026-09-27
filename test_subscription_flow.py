"""Test subscription flow via live HTTP against the running API server.

With the current payment architecture:
  - POST /api/client/checkout creates a checkout session (PENDING payment + PENDING subscription)
  - Subscription only becomes ACTIVE after the owner approves the manual payment
  - Manual methods (Cash Plus, Wafa Cash, CIH, crypto) are configured; Stripe is not
  - Checkout is idempotent per (user, plan, currency, method): a second checkout
    while a PENDING payment exists returns the SAME payment (200)
  - Unknown coupons return 404 ("Coupon not found"); invalid plan returns 404
  - POST /api/client/subscription/cancel returns 404 when there is no ACTIVE
    subscription (a PENDING checkout is not cancellable via this endpoint)

This test validates the HTTP API layer against the real response shapes:
  - checkout response: payment_id, subscription_id, payment_method_type,
    manual_instructions, manual_reference, expected_amount
  - payment history (GET /api/client/payments): plan_name, currency,
    original_amount, discount_amount, final_amount, coupon_code, status
"""
import httpx
import json
import sys

BASE = "http://localhost:8000"
_T = 30.0

# Patch httpx top-level functions to use longer timeout (default 5s is too short)
_original_post = httpx.post
_original_get = httpx.get

def _post(url, **kw):
    kw.setdefault("timeout", _T)
    return _original_post(url, **kw)

def _get(url, **kw):
    kw.setdefault("timeout", _T)
    return _original_get(url, **kw)

httpx.post = _post
httpx.get = _get

# A configured manual method for MAD (Cash Plus).
MANUAL_METHOD = "cash_plus"


def login(email, password):
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=_T)
    if r.status_code == 429:
        print(f"RATE LIMITED: {r.text}")
        sys.exit(1)
    r.raise_for_status()
    return r.json()["access_token"]


def test_subscription_flow():
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  PASS: {name}")
            passed += 1
        else:
            print(f"  FAIL: {name} {detail}")
            failed += 1

    # ── Setup ──────────────────────────────────────────────
    token = login("demo.client@ict-ea-demo.dev", "ClientDemo!2026")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Cancel any existing subscription (404 is fine — no active sub)
    r = httpx.post(f"{BASE}/api/client/subscription/cancel", headers=headers)

    # ── TEST 1: Checkout with MAD via Cash Plus (manual) ──
    print("\n=== TEST 1: Checkout with MAD (30_days plan, Cash Plus) ===")
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "30_days", "currency": "MAD", "payment_method": MANUAL_METHOD})
    check("Checkout returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    data = r.json()
    check("Response has success=true", data.get("success") is True)

    checkout = data.get("checkout", {})
    payment_id = checkout.get("payment_id")
    check("Response has payment_id", payment_id is not None, f"got: {payment_id}")
    check("Payment method type is manual",
          checkout.get("payment_method_type") == "manual",
          f"got: {checkout.get('payment_method_type')}")
    check("Manual instructions present",
          bool(checkout.get("manual_instructions")),
          "no manual_instructions")
    check("Manual reference present",
          bool(checkout.get("manual_reference")),
          "no manual_reference")

    sub_id_1 = checkout.get("subscription_id")
    check("Response has subscription_id", sub_id_1 is not None)
    # New checkout path returns expected_amount; the idempotent path (existing
    # PENDING payment for the same plan+currency+method) omits it.
    check("Expected amount > 0 (new path) or omitted (idempotent path)",
          checkout.get("expected_amount") is None or checkout.get("expected_amount", 0) > 0,
          f"got: {checkout.get('expected_amount')}")

    # ── TEST 2: Payment is PENDING before verification ────
    print("\n=== TEST 2: Payment is PENDING before verification ===")
    r = httpx.get(f"{BASE}/api/client/payments", headers=headers)
    payments = r.json().get("payments", [])
    latest = next((p for p in payments if p.get("id") == payment_id), None)
    check("Payment exists in history", latest is not None, f"got: {len(payments)} payments")
    if latest:
        check("Payment status=PENDING", latest.get("status") == "PENDING",
              f"got: {latest.get('status')}")
        check("History plan_name = 30 Days", latest.get("plan_name") == "30 Days",
              f"got: {latest.get('plan_name')}")
        check("History currency = MAD", latest.get("currency") == "MAD",
              f"got: {latest.get('currency')}")
        check("History original_amount > 0", latest.get("original_amount", 0) > 0,
              f"got: {latest.get('original_amount')}")
        check("History final_amount > 0", latest.get("final_amount", 0) > 0,
              f"got: {latest.get('final_amount')}")

    # ── TEST 3: Cancel + new checkout with WELCOME20 coupon ──
    print("\n=== TEST 3: Cancel + new checkout with WELCOME20 coupon ===")
    r = httpx.post(f"{BASE}/api/client/subscription/cancel", headers=headers)
    # No ACTIVE subscription -> 404 is the correct API behavior.
    check("Cancel returns 200 or 404 (no active sub)", r.status_code in (200, 404),
          f"got {r.status_code}")

    # Use a DIFFERENT payment method (wafa_cash) so the idempotency key
    # (plan+currency+method) differs from TEST 1 and a new payment is created
    # with the coupon applied. (cash_plus/15_days may already have a PENDING
    # payment from an earlier run, which would return the coupon-less payment.)
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "15_days", "currency": "MAD",
                         "payment_method": "wafa_cash", "coupon_code": "WELCOME20"})
    check("Checkout with coupon returns 200", r.status_code == 200,
          f"got {r.status_code}: {r.text[:200]}")
    data = r.json()
    checkout = data.get("checkout", {})
    payment_id_2 = checkout.get("payment_id")
    check("New payment_id created", payment_id_2 is not None and payment_id_2 != payment_id,
          f"got: {payment_id_2}")

    # Verify coupon math via payment history (checkout response does not carry it)
    r = httpx.get(f"{BASE}/api/client/payments", headers=headers)
    payments = r.json().get("payments", [])
    p2 = next((p for p in payments if p.get("id") == payment_id_2), None)
    check("Coupon payment in history", p2 is not None, "payment_id_2 not found in history")
    if p2:
        check("Coupon code preserved", p2.get("coupon_code") == "WELCOME20",
              f"got: {p2.get('coupon_code')}")
        original = p2.get("original_amount", 0)
        discount = p2.get("discount_amount", 0)
        final = p2.get("final_amount", 0)
        check("Original amount > 0", original > 0, f"got: {original}")
        check("Discount > 0 (WELCOME20 is 20%)", discount > 0, f"got: {discount}")
        check("Final = original - discount", abs(final - (original - discount)) < 0.01,
              f"got: final={final}, original={original}, discount={discount}")

    # ── TEST 4: Duplicate checkout is idempotent ──────────
    print("\n=== TEST 4: Duplicate checkout blocked (idempotency) ===")
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "30_days", "currency": "MAD", "payment_method": MANUAL_METHOD})
    check("Duplicate returns 200 (same payment) or 409", r.status_code in (200, 409),
          f"got: {r.status_code}")
    if r.status_code == 200:
        same = r.json().get("checkout", {}).get("payment_id") == payment_id
        check("Duplicate returns the SAME payment_id", same,
              f"got: {r.json().get('checkout', {}).get('payment_id')}")

    # ── TEST 5: Subscription history ──────────────────────
    print("\n=== TEST 5: Subscription history ===")
    r = httpx.get(f"{BASE}/api/client/subscription/history", headers=headers)
    check("History returns 200", r.status_code == 200, f"got: {r.status_code}")
    hist = r.json().get("subscriptions", [])
    check("History has >= 2 rows", len(hist) >= 2, f"got: {len(hist)}")

    # ── TEST 6: Invalid coupon returns clean error ─────────
    print("\n=== TEST 6: Invalid coupon returns clean error ===")
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "30_days", "currency": "MAD",
                         "payment_method": MANUAL_METHOD, "coupon_code": "FAKECOUPON"})
    # Unknown coupon -> 404 "Coupon not found" (CouponValidationError status_code=404)
    check("Invalid coupon returns 404", r.status_code == 404, f"got: {r.status_code}")
    detail = r.json().get("detail", "")
    check("Error mentions coupon", "coupon" in detail.lower(), f"got: {detail}")

    # ── TEST 7: Nonexistent plan returns 404 ──────────────
    print("\n=== TEST 7: Nonexistent plan returns 404 ===")
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "nonexistent-plan", "currency": "MAD",
                         "payment_method": MANUAL_METHOD})
    check("Nonexistent plan returns 404", r.status_code == 404, f"got: {r.status_code}")

    # ── TEST 8: Payment history from Payment table ─────────
    print("\n=== TEST 8: Payment history ===")
    r = httpx.get(f"{BASE}/api/client/payments", headers=headers)
    check("Payment history returns 200", r.status_code == 200, f"got: {r.status_code}")
    payments = r.json().get("payments", [])
    check("Payment history has >= 1 record", len(payments) >= 1, f"got: {len(payments)}")
    for p in payments:
        check(f"Payment {p.get('payment_number', '?')}: has status",
              p.get("status") in ("PENDING", "PAID", "FAILED", "CANCELLED", "PROCESSING",
                                  "PENDING_VERIFICATION", "SUBMITTED", "AWAITING_PAYMENT",
                                  "EXPIRED", "REJECTED"))
        check(f"Payment {p.get('payment_number', '?')}: amount > 0",
              float(p.get("final_amount", 0)) > 0)
        check(f"Payment {p.get('payment_number', '?')}: has currency",
              p.get("currency") in ("USD", "EUR", "MAD", "BTC", "ETH", "SOL", "USDT"))

    # ── TEST 9: Receipts (only exist for PAID payments) ────
    print("\n=== TEST 9: Receipts ===")
    r = httpx.get(f"{BASE}/api/client/receipts", headers=headers)
    check("Receipts returns 200", r.status_code == 200, f"got: {r.status_code}")
    receipts = r.json().get("receipts", [])
    check("Receipts list returned", isinstance(receipts, list))

    # ── TEST 10: Provider status ──────────────────────────
    print("\n=== TEST 10: Provider status ===")
    r = httpx.get(f"{BASE}/api/client/provider/status", headers=headers)
    check("Provider status returns 200", r.status_code == 200, f"got: {r.status_code}")
    provider = r.json()
    providers = provider.get("providers", [])
    manual_configured = any(p.get("is_manual") and p.get("is_configured") for p in providers)
    check("At least one manual method configured", manual_configured,
          f"got: {json.dumps(provider)[:300]}")

    # ── TEST 11: Plan details validation ──────────────────
    print("\n=== TEST 11: Plan validation ===")
    # 15_days/MAD/cash_plus may already have a PENDING payment from TEST 3 of an
    # earlier run, so the idempotent checkout returns 200 with the same payment
    # (or 409 if a duplicate guard fires).
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "15_days", "currency": "MAD", "payment_method": MANUAL_METHOD})
    check(f"Plan 15_days with MAD: valid request",
          r.status_code in (200, 409), f"got: {r.status_code}")

    # ── Cleanup ────────────────────────────────────────────
    print("\n=== Cleanup ===")
    r = httpx.post(f"{BASE}/api/client/subscription/cancel", headers=headers)
    check("Cleanup: cancel subscription", r.status_code in (200, 404))

    # ── Summary ────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
    print(f"{'='*60}")
    return failed == 0


if __name__ == "__main__":
    try:
        ok = test_subscription_flow()
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)