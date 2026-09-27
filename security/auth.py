"""
security.auth — unified re-export for all auth primitives.

Import from here when you need anything auth-related::

    from security.auth import (
        hash_password, verify_password,
        create_access_token, create_refresh_token, decode_token,
        Permission, has_permission, ROLE_PERMISSIONS,
        require_permission, require_role,
        get_current_user, get_optional_user, get_current_admin_user,
        log_event,
    )
"""
from __future__ import annotations

# password
from security.password import hash_password, verify_password  # noqa: F401

# jwt
from security.jwt_handler import (  # noqa: F401
    create_access_token,
    create_refresh_token,
    create_2fa_token,
    decode_token,
    hash_refresh_token,
)

# access control
from security.access_control import (  # noqa: F401
    Permission,
    ROLE_PERMISSIONS,
    ROLE_HIERARCHY,
    get_hierarchy_level,
    get_user_permissions,
    has_permission,
    seed_roles_and_permissions,
)

# dependencies
from security.dependencies import (  # noqa: F401
    get_current_admin_user,
    get_current_user,
    get_optional_user,
    require_permission,
    require_role,
)

# audit
from security.audit import log_event  # noqa: F401
