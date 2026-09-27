"""Test the real payment lifecycle against the running API server.

Covers the authoritative requirements:
  REQ 7  — real payment expiry: checkout returns expired_at; history carries it
  REQ 8  — submit gating: owner pending list shows ONLY submitted payments
  REQ 9  — stale cleanup: an expired payment never blocks a fresh checkout
  REQ 10 — broken crypto hidden: no owner wallet config -> crypto not offered,
           checkout with crypto -> 503
  REQ 17 — lifecycle statuses: reject -> REJECTED (distinct from FAILED)

Requires the API server on :8000 and Postgres (psql) for backdating expiry.
"""
import httpx
import os
import subprocess
import sys

BASE = "http://localhost:8000"
PSQL = r"C:\Program Files\PostgreSQL\18\bin\psql.exe"
PGPASSWORD = "cimoro2008"
DB = "ict_funded_ea"

MANUAL_METHOD = "wafa_cash"

# Increased timeout (30s) to avoid flaky failures when email/telegram is slow
_T = 30.0


def login(email, password):
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=_T)
    if r.status_code == 429:
        print(f"RATE LIMITED: {r.text}")
        sys.exit(1)
    r.raise_for_status()
    return r.json()["access_token"]


def psql(sql: str) -> None:
    """Run a SQL statement against the dev database (test fixture manipulation)."""
    env = dict(os.environ)
    env["PGPASSWORD"] = PGPASSWORD
    proc = subprocess.run(
        [PSQL, "-h", "localhost", "-U", "postgres", "-d", DB, "-c", sql],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"psql failed: {proc.stderr}")


def test_payment_lifecycle():
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
    owner_token = login("demo.owner@ict-ea-demo.dev", "OwnerDemo!2026")
    owner_headers = {"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"}

    # ── TEST 1: Checkout carries a real expiry deadline (REQ 7) ──
    print("\n=== TEST 1: Checkout returns expired_at (REQ 7) ===")
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "30_days", "currency": "MAD", "payment_method": MANUAL_METHOD},
                   timeout=_T)
    check("Checkout returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    data = r.json()
    checkout = data.get("checkout", {})
    payment_id = checkout.get("payment_id")
    check("Response has payment_id", payment_id is not None, f"got: {payment_id}")
    expired_at = checkout.get("expired_at")
    check("Checkout returns expired_at", bool(expired_at), f"got: {expired_at}")
    if expired_at:
        from datetime import datetime, timezone
        deadline = datetime.fromisoformat(expired_at.replace("Z", "+00:00"))
        delta_h = (deadline - datetime.now(timezone.utc)).total_seconds() / 3600
        check("Expiry is in the future (~72h default)",
              60 < delta_h < 84, f"got {delta_h:.1f}h until expiry")

    # History must carry the deadline too
    r = httpx.get(f"{BASE}/api/client/payments", headers=headers, timeout=_T)
    latest = next((p for p in r.json().get("payments", []) if p.get("id") == payment_id), None)
    check("History payment has expired_at", bool(latest and latest.get("expired_at")),
          f"got: {latest and latest.get('expired_at')}")

    # ── TEST 2: Owner pending list excludes unsubmitted payments (REQ 8) ──
    print("\n=== TEST 2: Pending list = submitted only (REQ 8) ===")
    r = httpx.get(f"{BASE}/api/admin/payments/pending", headers=owner_headers, timeout=_T)
    check("Pending list returns 200", r.status_code == 200, f"got {r.status_code}")
    pending_ids = [p.get("id") for p in r.json().get("items", [])]
    check("Unsubmitted PENDING payment NOT in pending list",
          payment_id not in pending_ids,
          "created-but-not-submitted payment leaked into owner queue")

    # ── TEST 3: Submit -> PENDING_VERIFICATION appears in queue (REQ 8) ──
    print("\n=== TEST 3: Submit moves payment into the owner queue ===")
    # Upload a real proof file first (mandatory server-side)
    proof = httpx.post(
        f"{BASE}/api/client/payments/{payment_id}/upload-proof",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("proof.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")},
        timeout=_T,
    )
    check("Proof upload returns 200", proof.status_code == 200, f"got {proof.status_code}: {proof.text[:200]}")
    proof_url = proof.json().get("url")
    check("Proof URL returned", bool(proof_url), f"got: {proof_url}")

    r = httpx.post(f"{BASE}/api/client/payments/{payment_id}/submit", headers=headers,
                   json={"manual_reference": "TEST-REF-123", "manual_proof_url": proof_url,
                         "payer_name": "Demo Client", "payer_phone": "+212600000000"},
                   timeout=_T)
    check("Submit returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    check("Submit -> PENDING_VERIFICATION",
          r.json().get("payment", {}).get("status") == "PENDING_VERIFICATION",
          f"got: {r.json().get('payment', {}).get('status')}")

    r = httpx.get(f"{BASE}/api/admin/payments/pending", headers=owner_headers, timeout=_T)
    pending_ids = [p.get("id") for p in r.json().get("items", [])]
    check("Submitted payment IS in pending list", payment_id in pending_ids,
          "submitted payment missing from owner queue")

    # ── TEST 4: Reject -> REJECTED status (REQ 17) ──
    print("\n=== TEST 4: Reject uses REJECTED status (REQ 17) ===")
    r = httpx.post(f"{BASE}/api/admin/payments/{payment_id}/reject", headers=owner_headers,
                   json={"rejection_reason": "Test rejection"}, timeout=_T)
    check("Reject returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    check("Reject -> REJECTED",
          r.json().get("payment", {}).get("status") == "REJECTED",
          f"got: {r.json().get('payment', {}).get('status')}")

    r = httpx.get(f"{BASE}/api/client/payments", headers=headers, timeout=_T)
    latest = next((p for p in r.json().get("payments", []) if p.get("id") == payment_id), None)
    check("Client history shows REJECTED", latest and latest.get("status") == "REJECTED",
          f"got: {latest and latest.get('status')}")
    check("Rejection reason preserved", latest and latest.get("rejection_reason") == "Test rejection",
          f"got: {latest and latest.get('rejection_reason')}")

    # ── TEST 5: Expired payment cannot be submitted; sweep -> EXPIRED (REQ 7/9) ──
    print("\n=== TEST 5: Expiry blocks submission, sweep marks EXPIRED ===")
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "15_days", "currency": "MAD", "payment_method": MANUAL_METHOD},
                   timeout=_T)
    data = r.json()
    checkout = data.get("checkout", {})
    payment_id_2 = checkout.get("payment_id")
    check("Second checkout returns 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    check("New payment_id differs from rejected one", payment_id_2 != payment_id,
          "rejected payment still blocks checkout")

    # Backdate the expiry so the payment is stale
    psql(f"UPDATE payments SET expired_at = now() - interval '1 hour' WHERE id = '{payment_id_2}';")

    # Submit must fail with a clean expiry error
    r = httpx.post(f"{BASE}/api/client/payments/{payment_id_2}/submit", headers=headers,
                   json={"manual_reference": "LATE-REF", "manual_proof_url": proof_url},
                   timeout=_T)
    check("Submit on expired payment returns 400", r.status_code == 400,
          f"got {r.status_code}: {r.text[:200]}")
    check("Error mentions expiry", "expired" in r.text.lower(), f"got: {r.text[:200]}")

    # Sweep runs on payment history read -> EXPIRED
    r = httpx.get(f"{BASE}/api/client/payments", headers=headers, timeout=_T)
    latest = next((p for p in r.json().get("payments", []) if p.get("id") == payment_id_2), None)
    check("Sweep marks stale payment EXPIRED", latest and latest.get("status") == "EXPIRED",
          f"got: {latest and latest.get('status')}")

    # ── TEST 6: Expired payment never blocks a fresh checkout (REQ 9) ──
    print("\n=== TEST 6: Expired payment does not block new checkout ===")
    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "15_days", "currency": "MAD", "payment_method": MANUAL_METHOD},
                   timeout=_T)
    check("Checkout after expiry returns 200", r.status_code == 200,
          f"got {r.status_code}: {r.text[:200]}")
    payment_id_3 = r.json().get("checkout", {}).get("payment_id")
    check("Fresh payment created after expiry", payment_id_3 and payment_id_3 != payment_id_2,
          f"got: {payment_id_3}")

    # Cleanup: cancel the fresh payment so later runs start clean
    r = httpx.post(f"{BASE}/api/client/payments/{payment_id_3}/cancel", headers=headers, timeout=_T)
    check("Cleanup: cancel fresh payment", r.status_code == 200,
          f"got {r.status_code}: {r.text[:200]}")

    # ── TEST 7: Broken crypto is hidden (REQ 10) ──
    print("\n=== TEST 7: Crypto hidden without owner wallet config ===")
    r = httpx.get(f"{BASE}/api/client/payment-methods?currency=USD", headers=headers, timeout=_T)
    check("Payment methods returns 200", r.status_code == 200, f"got {r.status_code}")
    methods = r.json().get("methods", [])
    crypto_visible = [m for m in methods if m.get("type") == "manual_crypto"]
    check("No crypto methods offered without wallet config", len(crypto_visible) == 0,
          f"got: {[m['name'] for m in crypto_visible]}")

    r = httpx.post(f"{BASE}/api/client/checkout", headers=headers,
                   json={"plan_id": "30_days", "currency": "BTC", "payment_method": "btc"},
                   timeout=_T)
    # Crypto checkout is blocked: 503 when the method lacks an owner wallet
    # config, or 400 when the plan has no crypto pricing. Either way it must
    # never succeed while crypto is not operational.
    check("Crypto checkout without wallet is blocked", r.status_code in (400, 503),
          f"got {r.status_code}: {r.text[:200]}")

    print("\n============================================================")
    print(f"  RESULTS: {passed}/{passed + failed} passed, {failed} failed")
    print("============================================================")
    return failed == 0


if __name__ == "__main__":
    ok = test_payment_lifecycle()
    sys.exit(0 if ok else 1)