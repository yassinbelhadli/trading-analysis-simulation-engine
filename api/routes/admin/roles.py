from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.db import get_session
from database.models import Permission as PermissionModel, Role, RolePermission, User
from security.auth import ROLE_HIERARCHY, get_hierarchy_level, has_permission, log_event, require_role

router = APIRouter(tags=["admin", "roles"])


@router.get("/roles")
async def list_roles(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    result = await session.execute(
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .order_by(Role.name)
    )
    roles = result.scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "is_system": r.is_system,
                "permissions": [
                    {"id": rp.permission.id, "resource": rp.permission.resource, "action": rp.permission.action}
                    for rp in (r.permissions or [])
                ],
            }
            for r in roles
        ]
    }


@router.get("/roles/{role_id}")
async def get_role(
    role_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    result = await session.execute(
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "permissions": [
            {"id": rp.permission.id, "resource": rp.permission.resource, "action": rp.permission.action}
            for rp in (role.permissions or [])
        ],
    }


@router.post("/roles")
async def create_role(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    if name in ROLE_HIERARCHY:
        raise HTTPException(status_code=403, detail="Cannot use a built-in role name")
    result = await session.execute(select(Role).where(Role.name == name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Role already exists")
    role = Role(name=name, description=body.get("description"), is_system=False)
    session.add(role)
    await session.flush()
    perm_ids = body.get("permission_ids", [])
    for pid in await _validate_permission_ids(session, current_user, perm_ids):
        session.add(RolePermission(role_id=role.id, permission_id=pid))
    audit_id = await log_event(session, "role.created", f"Role {name} created",
                                user_id=current_user.id, payload={"role_id": role.id})
    await session.commit()
    return {"id": role.id, "audit_id": audit_id, "message": "Role created"}


@router.patch("/roles/{role_id}")
async def update_role(
    role_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    result = await session.execute(
        select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=403, detail="Cannot modify system roles")
    # Hierarchy check: can't edit roles at or above your own level
    caller_level = get_hierarchy_level(current_user.role_rel.name if current_user.role_rel else "client")
    target_level = get_hierarchy_level(role.name)
    if target_level >= caller_level and current_user.role_rel.name != "owner":
        raise HTTPException(status_code=403, detail="Cannot modify roles at or above your level")
    if "name" in body:
        new_name = body["name"].strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Name required")
        if new_name in ROLE_HIERARCHY and new_name != role.name:
            raise HTTPException(status_code=403, detail="Cannot use a built-in role name")
        role.name = new_name
    if "description" in body:
        role.description = body["description"]
    if "permission_ids" in body:
        existing = await session.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        )
        for rp in existing.scalars().all():
            await session.delete(rp)
        for pid in await _validate_permission_ids(session, current_user, body["permission_ids"]):
            session.add(RolePermission(role_id=role.id, permission_id=pid))
    audit_id = await log_event(session, "role.updated", f"Role {role.name} updated",
                                user_id=current_user.id, payload={"role_id": role.id})
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "Role updated"}


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    result = await session.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system roles")
    # Hierarchy check
    caller_level = get_hierarchy_level(current_user.role_rel.name if current_user.role_rel else "client")
    target_level = get_hierarchy_level(role.name)
    if target_level >= caller_level and current_user.role_rel.name != "owner":
        raise HTTPException(status_code=403, detail="Cannot delete roles at or above your level")
    user_count = await session.execute(
        select(User).where(User.role_id == role_id, User.account_status != "deleted")
    )
    if user_count.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Role has users assigned")
    await session.delete(role)
    audit_id = await log_event(session, "role.deleted", f"Role {role.name} deleted",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "Role deleted"}


@router.get("/permissions")
async def list_permissions(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    result = await session.execute(select(PermissionModel).order_by(PermissionModel.resource, PermissionModel.action))
    perms = result.scalars().all()
    return {
        "items": [
            {"id": p.id, "resource": p.resource, "action": p.action, "description": p.description}
            for p in perms
        ]
    }


@router.post("/roles/assign")
async def assign_role(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    user_id = body.get("user_id")
    role_id = body.get("role_id")

    if not user_id or not role_id:
        raise HTTPException(status_code=400, detail="user_id and role_id required")

    user_result = await session.execute(
        select(User).options(selectinload(User.role_rel)).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_result = await session.execute(select(Role).where(Role.id == role_id))
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Hierarchy: can't assign roles at or above your level
    caller_level = get_hierarchy_level(current_user.role_rel.name if current_user.role_rel else "client")
    target_level = get_hierarchy_level(role.name)
    if target_level >= caller_level and current_user.role_rel.name != "owner":
        raise HTTPException(status_code=403, detail="Cannot assign roles at or above your level")
    # Prevent demoting the last owner
    if user.role_rel and user.role_rel.name == "owner" and role.name != "owner":
        owner_count = await session.execute(
            select(User).join(Role, User.role_id == Role.id).where(Role.name == "owner")
        )
        total_owners = len(owner_count.scalars().all())
        if total_owners <= 1:
            raise HTTPException(status_code=403, detail="Cannot demote the last owner")

    old_role = user.role_rel.name if user.role_rel else None
    user.role_id = role_id
    audit_id = await log_event(session, "role.assigned",
                                f"Role {role.name} assigned to user {user_id}",
                                user_id=current_user.id,
                                payload={"user_id": user_id, "from_role": old_role, "to_role": role.name})
    await session.commit()

    return {"success": True, "audit_id": audit_id, "message": f"Role changed to {role.name}"}


async def _validate_permission_ids(
    session: AsyncSession,
    caller: User,
    permission_ids: list,
) -> list[str]:
    """Validate a permission-id list before attaching it to a role.

    Rules (both are privilege-escalation guards):
      1. Every id must reference an existing Permission row.
      2. A non-owner caller may only grant permissions they themselves hold
         (a user with ROLES_CREATE must not be able to hand out SYSTEM_SECRETS
         or any other permission they do not own).
    """
    if not isinstance(permission_ids, list):
        raise HTTPException(status_code=400, detail="permission_ids must be a list")
    if not permission_ids:
        return []

    result = await session.execute(
        select(PermissionModel).where(PermissionModel.id.in_(permission_ids))
    )
    found = result.scalars().all()
    found_ids = {p.id for p in found}
    missing = [pid for pid in permission_ids if pid not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown permission_ids: {missing}")

    if caller.role_rel and caller.role_rel.name == "owner":
        return permission_ids

    for perm in found:
        perm_str = f"{perm.resource}.{perm.action}"
        if not await has_permission(session, caller, perm_str):
            raise HTTPException(
                status_code=403,
                detail=f"You cannot grant permission '{perm_str}' because you do not hold it",
            )
    return permission_ids
