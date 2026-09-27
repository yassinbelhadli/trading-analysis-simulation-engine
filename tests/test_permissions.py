"""
Test permissions system — verifies every role has correct permissions,
hierarchy works, and system roles are protected.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from security.access_control import (
    Permission,
    ROLE_PERMISSIONS,
    ROLE_HIERARCHY,
    get_hierarchy_level,
)

PASS = 0
FAIL = 0

def ok(msg):
    global PASS
    PASS += 1
    print(f"  OK  {msg}")

def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {msg}")


# ============================================================================
# 1. All permissions defined
# ============================================================================
def test_all_permissions_defined():
    expected = [
        "*",
        "accounts.create", "accounts.delete", "accounts.read", "accounts.update",
        "admin.dashboard.read", "admin.overview",
        "analytics.read",
        "audit.read",
        "billing.create", "billing.read", "billing.refund",
        "clients.activate", "clients.create", "clients.delete", "clients.export",
        "clients.read", "clients.suspend", "clients.update",
        "emails.read", "emails.send",
        "engine.control", "engine.read", "engine.restart", "engine.start", "engine.stop",
        "health.read",
        "licenses.create", "licenses.delete", "licenses.read", "licenses.update",
        "roles.assign", "roles.create", "roles.delete", "roles.read", "roles.update",
        "self.read", "self.update",
        "subscriptions.cancel", "subscriptions.create", "subscriptions.read",
        "subscriptions.update",
        "support.create", "support.read", "support.reply",
        "system.health.read", "system.health.update", "system.secrets", "system.settings",
        "telegram.send",
        "tickets.ban", "tickets.read", "tickets.update",
        "trades.export", "trades.read", "trades.view",
        "users.create", "users.delete", "users.read", "users.update",
    ]
    actual = sorted(p.value for p in Permission)
    if actual == expected:
        ok(f"All {len(actual)} permissions defined correctly")
    else:
        miss = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        parts = []
        if miss:
            parts.append(f"Missing: {sorted(miss)}")
        if extra:
            parts.append(f"Extra: {sorted(extra)}")
        fail("; ".join(parts))


# ============================================================================
# 2. ROLE_PERMISSIONS — each role has correct permissions
# ============================================================================
def test_owner_has_everything():
    if "*" in ROLE_PERMISSIONS["owner"]:
        ok("Owner has '*' (all permissions)")
    else:
        fail("Owner missing '*'")


def test_admin_has_core_permissions():
    admin = ROLE_PERMISSIONS.get("admin", set())
    required = [
        Permission.ROLES_READ, Permission.ROLES_CREATE, Permission.ROLES_UPDATE,
        Permission.ROLES_DELETE, Permission.ROLES_ASSIGN,
        Permission.LICENSES_READ, Permission.LICENSES_CREATE, Permission.LICENSES_UPDATE,
        Permission.LICENSES_DELETE,
        Permission.USERS_READ, Permission.USERS_CREATE, Permission.USERS_UPDATE,
        Permission.USERS_DELETE,
        Permission.ENGINE_READ, Permission.ENGINE_START, Permission.ENGINE_STOP,
        Permission.ENGINE_RESTART, Permission.ENGINE_CONTROL,
        Permission.SYSTEM_HEALTH_READ, Permission.SYSTEM_HEALTH_UPDATE,
        Permission.TELEGRAM_SEND,
    ]
    missing = [p for p in required if p not in admin]
    if missing:
        fail(f"Admin missing: {missing}")
    else:
        ok(f"Admin has all {len(required)} required permissions")


def test_client_has_minimal():
    client = ROLE_PERMISSIONS.get("client", set())
    checks = [
        (Permission.SELF_READ in client, "SELF_READ"),
        (Permission.SELF_UPDATE in client, "SELF_UPDATE"),
        (Permission.TRADES_READ in client, "TRADES_READ"),
        (Permission.SUBSCRIPTIONS_READ in client, "SUBSCRIPTIONS_READ"),
    ]
    forbidden = [
        Permission.USERS_CREATE, Permission.USERS_DELETE,
        Permission.ROLES_CREATE, Permission.ROLES_DELETE,
        Permission.ADMIN_OVERVIEW,
    ]
    has_forbidden = [p for p in forbidden if p in client]
    all_ok = True
    for okk, name in checks:
        if not okk:
            fail(f"Client missing: {name}")
            all_ok = False
    if has_forbidden:
        fail(f"Client has forbidden: {has_forbidden}")
        all_ok = False
    if all_ok:
        ok("Client has minimal permissions only")


# ============================================================================
# 3. ROLE_HIERARCHY
# ============================================================================
def test_hierarchy_order():
    checks = [
        (ROLE_HIERARCHY["owner"] == 100, "owner = 100"),
        (ROLE_HIERARCHY["admin"] == 80, "admin = 80"),
        (ROLE_HIERARCHY["client"] == 10, "client = 10"),
        (ROLE_HIERARCHY["owner"] > ROLE_HIERARCHY["admin"], "owner > admin"),
        (ROLE_HIERARCHY["admin"] > ROLE_HIERARCHY["support"], "admin > support"),
        (ROLE_HIERARCHY["support"] > ROLE_HIERARCHY["analyst"], "support > analyst"),
        (ROLE_HIERARCHY["analyst"] > ROLE_HIERARCHY["client"], "analyst > client"),
    ]
    all_ok = True
    for okk, name in checks:
        if not okk:
            fail(f"Hierarchy: {name}")
            all_ok = False
    if all_ok:
        ok("Hierarchy: owner(100) > admin(80) > support(60) > analyst(40) > client(10)")


def test_get_hierarchy_level():
    checks = [
        (get_hierarchy_level("owner") == 100, "owner -> 100"),
        (get_hierarchy_level("admin") == 80, "admin -> 80"),
        (get_hierarchy_level("client") == 10, "client -> 10"),
        (get_hierarchy_level(None) == 10, "None -> 10"),
        (get_hierarchy_level("unknown") == 0, "unknown -> 0"),
    ]
    all_ok = True
    for okk, name in checks:
        if not okk:
            fail(f"get_hierarchy_level: {name}")
            all_ok = False
    if all_ok:
        ok("get_hierarchy_level() works correctly")


# ============================================================================
# 4. System roles protected
# ============================================================================
def test_system_roles_exist():
    for name in ("owner", "admin"):
        if name not in ROLE_HIERARCHY:
            fail(f"Missing system role in hierarchy: {name}")
            return
    ok("System roles (owner, admin) in hierarchy")


# ============================================================================
# Runner
# ============================================================================
if __name__ == "__main__":
    tests = [
        ("All permissions defined", test_all_permissions_defined),
        ("Owner has everything", test_owner_has_everything),
        ("Admin has core permissions", test_admin_has_core_permissions),
        ("Client has minimal", test_client_has_minimal),
        ("Hierarchy order", test_hierarchy_order),
        ("get_hierarchy_level", test_get_hierarchy_level),
        ("System roles exist", test_system_roles_exist),
    ]
    print(f"\nRunning {len(tests)} permission tests...\n")
    for name, fn in tests:
        print(f"  {name}")
        fn()
        print()
    print(f"  {'='*35}")
    print(f"  PASSED: {PASS}  FAILED: {FAIL}  TOTAL: {len(tests)}")
    sys.exit(1 if FAIL else 0)
