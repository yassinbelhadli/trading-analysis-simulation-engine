from __future__ import annotations

import logging
from functools import wraps
from typing import Callable

from fastapi import HTTPException

from security.access_control import Permission

logger = logging.getLogger(__name__)


def require_permission(permission: str | Permission) -> Callable:
    """
    Decorator that checks the current user has the given permission.
    Usage::

        @router.post("/clients")
        @require_permission("clients.create")
        async def create_client(payload: ..., current_user: User = Depends(get_current_user)):
            ...

    The decorator expects a ``current_user`` kwarg of type ``User`` in the route handler.
    """
    perm_str = permission.value if isinstance(permission, Permission) else permission

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")

            from database.db import async_session_factory
            from security.access_control import has_permission

            async with async_session_factory() as session:
                allowed = await has_permission(session, current_user, perm_str)
                if not allowed:
                    raise HTTPException(status_code=403, detail=f"Missing permission: {perm_str}")
            return await func(*args, **kwargs)

        return wrapper

    return decorator
