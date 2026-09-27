"""REQ 3 — EA Downloads -> EA Updates: artifact extension preservation.

Verifies against the running API server (:8000) that:

  * Admin upload of a non-.ex5 artifact (e.g. .zip) stores it with the
    ORIGINAL extension preserved (ict_ea_v<version>.zip), not a forced .ex5.
  * The client download endpoint serves the real stored filename so the
    client receives the correct extension.
  * The build is visible to clients only after approval.

Requires the API server on :8000 and Postgres.
"""
import httpx
import io
import sys

BASE = "http://localhost:8000"
VERSION = "9.9.9"
ZIP_NAME = "ict_funded_ea_package.zip"


def login(email, password):
    r = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if r.status_code == 429:
        print(f"RATE LIMITED: {r.text}")
        sys.exit(1)
    r.raise_for_status()
    return r.json()["access_token"]


def main():
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

    print("=" * 60)
    print("REQ 3: EA UPDATES — EXTENSION PRESERVATION")
    print("=" * 60)

    admin_token = login("demo.admin@ict-ea-demo.dev", "AdminDemo!2026")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    client_token = login("demo.client@ict-ea-demo.dev", "ClientDemo!2026")
    client_headers = {"Authorization": f"Bearer {client_token}"}

    build_id = None
    try:
        # ── 1. Create release ──────────────────────────────────────────
        print("\n--- Create release ---")
        r = httpx.post(f"{BASE}/api/admin/ea-builds", headers=admin_headers,
                       json={"version": VERSION, "release_notes": "REQ3 test", "changelog": "ext preservation"})
        check("Create build 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        build_id = r.json().get("id")
        check("Build id returned", bool(build_id), f"got: {build_id}")

        # ── 2. Upload a .zip artifact (>1 MB minimum) ─────────────────
        print("\n--- Upload .zip artifact ---")
        payload = b"PK\x03\x04" + b"\x00" * (1024 * 1024 + 64)  # fake zip, >1 MB
        files = {"file": (ZIP_NAME, io.BytesIO(payload), "application/zip")}
        r = httpx.post(f"{BASE}/api/admin/ea-builds/{build_id}/upload", headers=admin_headers, files=files)
        check("Upload 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        data = r.json()
        check("Stored name preserves .zip extension",
              data.get("windows_file") == f"ict_ea_v{VERSION}.zip",
              f"got: {data.get('windows_file')}")

        # ── 3. Client cannot see unapproved build ─────────────────────
        print("\n--- Approval gating ---")
        r = httpx.get(f"{BASE}/api/client/ea", headers=client_headers)
        check("Client EA info 200", r.status_code == 200, f"got {r.status_code}")
        visible = [b for b in r.json().get("changelog", []) if b.get("version") == VERSION]
        check("Unapproved build hidden from clients", len(visible) == 0, f"visible: {len(visible)}")

        # ── 4. Approve, then client sees it ───────────────────────────
        r = httpx.post(f"{BASE}/api/admin/ea-builds/{build_id}/approve", headers=admin_headers)
        check("Approve 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        r = httpx.get(f"{BASE}/api/client/ea", headers=client_headers)
        visible = [b for b in r.json().get("changelog", []) if b.get("version") == VERSION]
        check("Approved build visible to clients", len(visible) == 1, f"visible: {len(visible)}")
        check("windows_available true", bool(visible and visible[0].get("windows_available")),
              f"got: {visible[0] if visible else None}")

        # ── 5. Download serves the real stored filename ───────────────
        print("\n--- Download filename ---")
        r = httpx.get(f"{BASE}/api/client/ea/download/{build_id}", headers=client_headers)
        check("Download 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        cd = r.headers.get("content-disposition", "")
        check("Content-Disposition carries .zip filename",
              f"ict_ea_v{VERSION}.zip" in cd,
              f"got: {cd}")
        check("Downloaded bytes match upload", len(r.content) == len(payload),
              f"got {len(r.content)} vs {len(payload)}")
    finally:
        # ── 6. Cleanup ────────────────────────────────────────────────
        if build_id:
            r = httpx.delete(f"{BASE}/api/admin/ea-builds/{build_id}", headers=admin_headers)
            check("Cleanup delete 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")

    print("\n" + "=" * 60)
    print(f"REQ 3 RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)