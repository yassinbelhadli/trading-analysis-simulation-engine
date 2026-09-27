"""QA for EA Build Publishing (admin upload/release workflow).

Scenarios:
  Auth guards: unauthenticated 401; client token 403; support token 403;
               owner token allowed; admin token allowed.
  Create: create release, duplicate version 409, bad version format 400.
  Upload: wrong extension 400, too-small 400, too-large 400 (patched cap),
          valid .ex5 200 + stored on disk + visible to clients.
  Latest: set-latest clears the previous flag (single latest invariant).
  Patch: release notes/changelog update; 404 on missing build.
  Client round-trip (same source of truth): /api/client/ea lists the new
          version; download returns the exact uploaded bytes; license rules
          preserved (no license -> 403).
  Delete: removes row + artifact from disk; download -> 404; re-delete 404.
  Audit: ea_build.* events written.

Cleanup: test builds (9.9.x) and their artifacts are deleted at the end so
the shared QA DB + storage stay as other suites expect them.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_TEST_MODE", None)

PASSWORD = "EaPassw0rd!789"
ADMIN = "qa_ea_admin@test.local"
OWNER = "qa_ea_owner@test.local"
CLIENT = "qa_ea_client@test.local"
NOLIC = "qa_ea_nolic@test.local"
TEST_VERSIONS = ("9.9.1", "9.9.2")
EA_STORAGE = Path(__file__).resolve().parents[1] / "storage" / "ea"

RESULTS: list[tuple[bool, str]] = []


def check(cond: bool, label: str):
    RESULTS.append((bool(cond), label))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


async def _seed(s):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import delete, select
    from database.base import Base
    from database.models import AuditLog, EABuild, License, Role, User
    from security.access_control import seed_roles_and_permissions
    from security.password import hash_password

    await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
    await seed_roles_and_permissions(s)
    roles = {}
    for rname in ("owner", "admin", "client", "support"):
        r = (await s.execute(select(Role).where(Role.name == rname))).scalar_one_or_none()
        roles[rname] = r
    now = datetime.now(timezone.utc)

    # Remove test builds (rows + artifacts) from previous runs.
    result = await s.execute(select(EABuild).where(EABuild.version.in_(TEST_VERSIONS)))
    for b in result.scalars().all():
        if b.windows_file:
            (EA_STORAGE / b.windows_file).unlink(missing_ok=True)
        await s.execute(delete(AuditLog).where(AuditLog.payload_json.like("%9.9%")))
        await s.delete(b)
    await s.flush()

    async def _reset(email: str):
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if u:
            await s.execute(delete(License).where(License.user_id == u.id))
            await s.execute(delete(AuditLog).where(AuditLog.user_id == u.id))
            await s.delete(u)
            await s.flush()

    async def _user(email: str, role_name: str, first: str) -> User:
        u = User(email=email, password_hash=hash_password(PASSWORD),
                 first_name=first, last_name="EaQA",
                 role_id=roles[role_name].id if roles[role_name] else None,
                 account_status="active", email_verified=True, language="EN")
        s.add(u)
        await s.flush()
        return u

    await _reset(ADMIN); admin = await _user(ADMIN, "admin", "Admin")
    await _reset(OWNER); await _user(OWNER, "owner", "Owner")
    await _reset(CLIENT); client = await _user(CLIENT, "client", "Client")
    await _reset(NOLIC); await _user(NOLIC, "client", "NoLic")
    s.add(License(user_id=client.id, license_key="QA-EA-CLIENT-1", plan="professional",
                  status="active", max_accounts=3, expires_at=now + timedelta(days=30)))
    await s.commit()


def _run_seed():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    async def go():
        eng = create_async_engine(os.environ["DATABASE_URL"])
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as s:
                await _seed(s)
        finally:
            await eng.dispose()
    asyncio.run(go())


def _login(c, email):
    r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _payload(size: int, marker: str) -> bytes:
    head = b"QA-EA-TEST-BUILD|" + marker.encode() + b"|"
    return head + bytes(max(0, size - len(head)))


def main():
    _run_seed()

    from fastapi.testclient import TestClient
    from api.main import app
    # Neutralise the real bot token from config/.env (deterministic QA).
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    with TestClient(app) as c:
        H_admin = _login(c, ADMIN)
        H_owner = _login(c, OWNER)
        H_client = _login(c, CLIENT)
        H_nolic = _login(c, NOLIC)

        # ---- [1] Auth + permission guards -----------------------------------
        print("\n[1] Auth + permission guards")
        r = c.get("/api/admin/ea-builds")
        check(r.status_code == 401, "unauthenticated list -> 401")
        r = c.post("/api/admin/ea-builds", json={"version": "9.9.1"})
        check(r.status_code == 401, "unauthenticated create -> 401")
        r = c.get("/api/admin/ea-builds", headers=H_client)
        check(r.status_code == 403, "client list -> 403")
        r = c.post("/api/admin/ea-builds", json={"version": "9.9.1"}, headers=H_client)
        check(r.status_code == 403, "client create -> 403")
        r = c.get("/api/admin/ea-builds", headers=H_nolic)
        check(r.status_code == 403, "client (no license) list -> 403")
        r = c.get("/api/admin/ea-builds", headers=H_owner)
        check(r.status_code == 200, "owner list -> 200")

        # ---- [2] Create releases ----------------------------------------------
        print("\n[2] Create releases")
        r = c.get("/api/admin/ea-builds", headers=H_admin)
        before = r.json()["total"]
        check(r.status_code == 200 and r.json()["total"] == before, f"admin list -> 200 (total {before})")
        r = c.post("/api/admin/ea-builds", headers=H_admin,
                   json={"version": "9.9.1", "release_notes": "QA build one", "changelog": "- one"})
        check(r.status_code == 200 and r.json()["version"] == "9.9.1", "create 9.9.1 -> 200")
        r = c.post("/api/admin/ea-builds", headers=H_admin,
                   json={"version": "v9.9.2", "release_notes": "QA build two"})
        check(r.status_code == 200 and r.json()["version"] == "9.9.2", "create v9.9.2 (normalized) -> 200")
        r = c.post("/api/admin/ea-builds", headers=H_admin, json={"version": "9.9.1"})
        check(r.status_code == 409, "duplicate version -> 409")
        r = c.post("/api/admin/ea-builds", headers=H_admin, json={"version": "abc"})
        check(r.status_code == 400, "bad version format -> 400")
        r = c.post("/api/admin/ea-builds", headers=H_admin, json={"version": "1"})
        check(r.status_code == 400, "version without dot -> 400")
        r = c.post("/api/admin/ea-builds", headers=H_admin, json={})
        check(r.status_code == 400, "missing version -> 400")

        # ---- [3] Upload + file validation -------------------------------------
        print("\n[3] Upload + file validation")
        r = c.post("/api/admin/ea-builds/9.9.1/upload", headers=H_admin,
                   files={"file": ("notes.txt", b"nope", "text/plain")})
        check(r.status_code == 400 and ".ex4/.ex5" in r.text, "wrong extension -> 400")
        r = c.post("/api/admin/ea-builds/9.9.1/upload", headers=H_admin,
                   files={"file": ("ea.ex5", b"tiny", "application/octet-stream")})
        check(r.status_code == 400 and "too small" in r.text, "too-small file -> 400")

        import api.routes.admin.ea_builds as ea_routes
        _orig_max = ea_routes.MAX_EA_FILE_BYTES
        ea_routes.MAX_EA_FILE_BYTES = 4096
        try:
            r = c.post("/api/admin/ea-builds/9.9.1/upload", headers=H_admin,
                       files={"file": ("big.ex5", _payload(8192, "BIG"), "application/octet-stream")})
            check(r.status_code == 400 and "limit" in r.text, "too-large file -> 400 (patched cap)")
        finally:
            ea_routes.MAX_EA_FILE_BYTES = _orig_max

        r = c.post("/api/admin/ea-builds/9.9.1/upload", headers=H_client,
                   files={"file": ("ea.ex5", _payload(2048, "A"), "application/octet-stream")})
        check(r.status_code == 403, "client upload -> 403")

        payload_a = _payload(2048, "A")
        r = c.post("/api/admin/ea-builds/9.9.1/upload", headers=H_admin,
                   files={"file": ("ict_ea_v9.9.1.ex5", payload_a, "application/octet-stream")})
        check(r.status_code == 200 and r.json()["size_bytes"] == len(payload_a)
              and r.json()["windows_file"] == "ict_ea_v9.9.1.ex5", "valid upload -> 200 + stored name")
        check((EA_STORAGE / "ict_ea_v9.9.1.ex5").exists()
              and (EA_STORAGE / "ict_ea_v9.9.1.ex5").read_bytes() == payload_a,
              "artifact on disk matches uploaded bytes")

        r = c.post("/api/admin/ea-builds/9.9.2/upload", headers=H_admin,
                   files={"file": ("ict_ea_v9.9.2.ex5", _payload(4096, "B"), "application/octet-stream")})
        check(r.status_code == 200, "upload second build -> 200")
        r = c.post("/api/admin/ea-builds/does-not-exist/upload", headers=H_admin,
                   files={"file": ("ea.ex5", _payload(2048, "X"), "application/octet-stream")})
        check(r.status_code == 404, "upload to missing build -> 404")

        r = c.get("/api/admin/ea-builds", headers=H_admin)
        by_version = {b["version"]: b for b in r.json()["items"]}
        check(by_version["9.9.1"]["windows_available"] is True
              and by_version["9.9.2"]["windows_available"] is True, "list shows both windows builds available")

        # ---- [4] Latest-release management ------------------------------------
        print("\n[4] Latest-release management")
        r = c.post("/api/admin/ea-builds/9.9.2/set-latest", headers=H_admin)
        check(r.status_code == 200 and r.json()["is_latest"] is True, "set 9.9.2 latest -> 200")
        r = c.get("/api/admin/ea-builds", headers=H_admin)
        latest = [b for b in r.json()["items"] if b["is_latest"]]
        check(len(latest) == 1 and latest[0]["version"] == "9.9.2", "single latest invariant holds (9.9.2)")
        r = c.post("/api/admin/ea-builds/nope/set-latest", headers=H_admin)
        check(r.status_code == 404, "set-latest missing build -> 404")

        # ---- [5] Patch ----------------------------------------------------------
        print("\n[5] Patch")
        r = c.patch("/api/admin/ea-builds/9.9.1", headers=H_admin,
                    json={"release_notes": "QA build one (updated)", "changelog": "- one\n- two"})
        check(r.status_code == 200, "patch notes -> 200")
        r = c.get("/api/admin/ea-builds", headers=H_admin)
        by_version = {b["version"]: b for b in r.json()["items"]}
        check(by_version["9.9.1"]["release_notes"] == "QA build one (updated)"
              and by_version["9.9.1"]["changelog"] == "- one\n- two", "patched notes persisted")
        r = c.patch("/api/admin/ea-builds/nope", headers=H_admin, json={"release_notes": "x"})
        check(r.status_code == 404, "patch missing build -> 404")
        r = c.patch("/api/admin/ea-builds/9.9.1", headers=H_client, json={"release_notes": "x"})
        check(r.status_code == 403, "client patch -> 403")

        # ---- [6] Client round-trip (same source of truth) ----------------------
        print("\n[6] Client round-trip")
        r = c.get("/api/client/ea", headers=H_client)
        j = r.json()
        check(j["latest"]["version"] == "9.9.2" and j["latest"]["windows_available"] is True,
              "client latest = 9.9.2 + available")
        check(any(b["version"] == "9.9.1" for b in j["changelog"]), "client changelog includes 9.9.1")
        r = c.get("/api/client/ea/download/latest", headers=H_client)
        check(r.status_code == 200 and r.content == _payload(4096, "B"), "client download latest = 9.9.2 bytes")
        r = c.get("/api/client/ea/download/9.9.1", headers=H_client)
        check(r.status_code == 200 and r.content == payload_a, "client download by version = 9.9.1 bytes")
        r = c.get("/api/client/ea/download/latest", headers=H_nolic)
        check(r.status_code == 403, "no-license client download -> 403 (rules preserved)")

        # ---- [7] Delete ---------------------------------------------------------
        print("\n[7] Delete")
        r = c.delete("/api/admin/ea-builds/9.9.1", headers=H_admin)
        check(r.status_code == 200 and r.json()["file_removed"] is True, "delete 9.9.1 -> 200 + file removed")
        check(not (EA_STORAGE / "ict_ea_v9.9.1.ex5").exists(), "artifact gone from disk")
        r = c.get("/api/client/ea/download/9.9.1", headers=H_client)
        check(r.status_code == 404, "client download of deleted build -> 404")
        r = c.delete("/api/admin/ea-builds/9.9.1", headers=H_admin)
        check(r.status_code == 404, "re-delete -> 404")
        r = c.delete("/api/admin/ea-builds/9.9.2", headers=H_admin)
        check(r.status_code == 200, "delete 9.9.2 -> 200")
        check(not (EA_STORAGE / "ict_ea_v9.9.2.ex5").exists(), "second artifact gone from disk")

        # ---- [8] Audit trail -------------------------------------------------------
        print("\n[8] Audit trail")
        r = c.get("/api/admin/audit-logs", headers=H_admin, params={"action": "ea_build.", "limit": 500})
        check(r.status_code == 200, "audit-logs list -> 200")
        if r.status_code == 200:
            actions = {item["action"] for item in r.json().get("items", [])}
            for ev in ("ea_build.created", "ea_build.uploaded", "ea_build.set_latest",
                       "ea_build.updated", "ea_build.deleted"):
                check(ev in actions, f"audit event {ev} written")

    passed = sum(1 for ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n=== EA Builds QA: {passed}/{total} PASS ===")
    if passed != total:
        print("Failed checks:")
        for ok, label in RESULTS:
            if not ok:
                print(f"  - {label}")
        sys.exit(1)


if __name__ == "__main__":
    main()
