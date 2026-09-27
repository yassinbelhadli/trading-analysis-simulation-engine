from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from database.db import async_session_factory
from database.repositories.license_repository import LicenseRepository
from database.repositories.user_repository import UserRepository
from security.license_gen import generate_license_key

admin_licenses_router = APIRouter()


class CreateLicenseRequest(BaseModel):
    user_id: str
    plan: str = "standard"
    max_accounts: int = 1
    expires_in_days: Optional[int] = None


class UpdateLicenseRequest(BaseModel):
    plan: Optional[str] = None
    status: Optional[str] = None
    max_accounts: Optional[int] = None


@admin_licenses_router.get("/licenses")
async def list_licenses(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
):
    async with async_session_factory() as session:
        from sqlalchemy import select
        from database.models import License
        stmt = select(License).order_by(License.created_at.desc()).limit(limit).offset(offset)
        if status:
            stmt = stmt.where(License.status == status)
        result = await session.execute(stmt)
        licenses = list(result.scalars().all())
        result_list = []
        for lic in licenses:
            entry = {
                "id": lic.id,
                "user_id": lic.user_id,
                "license_key": lic.license_key,
                "plan": lic.plan,
                "status": lic.status,
                "max_accounts": lic.max_accounts,
                "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
                "bound_account_id": lic.bound_account_id,
                "bound_at": lic.bound_at.isoformat() if lic.bound_at else None,
                "telegram_id": lic.telegram_id,
                "transfer_locked": lic.transfer_locked,
                "created_at": lic.created_at.isoformat(),
            }
            if lic.user:
                entry["telegram_username"] = lic.user.telegram_username
            result_list.append(entry)
        return result_list


@admin_licenses_router.get("/licenses/{license_id}")
async def get_license(license_id: str):
    async with async_session_factory() as session:
        repo = LicenseRepository(session)
        lic = await repo.get_by_id(license_id)
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")
        entry = {
            "id": lic.id,
            "user_id": lic.user_id,
            "license_key": lic.license_key,
            "plan": lic.plan,
            "status": lic.status,
            "max_accounts": lic.max_accounts,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
            "bound_account_id": lic.bound_account_id,
            "bound_at": lic.bound_at.isoformat() if lic.bound_at else None,
            "telegram_id": lic.telegram_id,
            "transfer_locked": lic.transfer_locked,
            "created_at": lic.created_at.isoformat(),
        }
        if lic.user:
            entry["telegram_username"] = lic.user.telegram_username
        return entry


@admin_licenses_router.post("/licenses")
async def create_license(body: CreateLicenseRequest):
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(body.user_id)
        if not user:
            try:
                tid = int(body.user_id)
                user = await user_repo.get_by_telegram_id(tid)
            except (ValueError, TypeError):
                pass
        if not user:
            from sqlalchemy import select
            from database.models import User
            stmt = select(User).where(User.telegram_username == body.user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        repo = LicenseRepository(session)
        key = generate_license_key()
        expires_at = None
        if body.expires_in_days:
            expires_at = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59)
            expires_at = expires_at.replace(day=expires_at.day + body.expires_in_days)

        lic = await repo.create(
            user_id=user.id,
            license_key=key,
            plan=body.plan,
            max_accounts=body.max_accounts,
            expires_at=expires_at,
        )
        await session.commit()
        return {
            "id": lic.id,
            "user_id": lic.user_id,
            "license_key": lic.license_key,
            "plan": lic.plan,
            "status": lic.status,
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        }


@admin_licenses_router.patch("/licenses/{license_id}")
async def update_license(license_id: str, body: UpdateLicenseRequest):
    async with async_session_factory() as session:
        repo = LicenseRepository(session)
        lic = await repo.get_by_id(license_id)
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")

        if body.plan is not None:
            lic.plan = body.plan
        if body.status is not None:
            lic.status = body.status
        if body.max_accounts is not None:
            lic.max_accounts = body.max_accounts

        await session.commit()
        return {"status": "updated", "license_id": license_id}


@admin_licenses_router.post("/licenses/{license_id}/activate")
async def activate_license(license_id: str):
    async with async_session_factory() as session:
        repo = LicenseRepository(session)
        lic = await repo.get_by_id(license_id)
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")
        lic.status = "active"
        await session.commit()
        return {"status": "activated", "license_id": license_id}


@admin_licenses_router.post("/licenses/{license_id}/deactivate")
async def deactivate_license(license_id: str):
    async with async_session_factory() as session:
        repo = LicenseRepository(session)
        lic = await repo.get_by_id(license_id)
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")
        lic.status = "inactive"
        await session.commit()
        return {"status": "deactivated", "license_id": license_id}


@admin_licenses_router.post("/licenses/{license_id}/unbind")
async def unbind_license(license_id: str):
    async with async_session_factory() as session:
        repo = LicenseRepository(session)
        lic = await repo.get_by_id(license_id)
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")
        lic.telegram_id = None
        lic.bound_at = None
        lic.bound_account_id = None
        lic.status = "active"
        await session.commit()
        return {"status": "unbound", "license_id": license_id}


@admin_licenses_router.post("/licenses/{license_id}/reset")
async def reset_license(license_id: str):
    async with async_session_factory() as session:
        repo = LicenseRepository(session)
        lic = await repo.get_by_id(license_id)
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")
        lic.telegram_id = None
        lic.bound_at = None
        lic.bound_account_id = None
        lic.transfer_locked = False
        lic.status = "active"
        await session.commit()
        return {"status": "reset", "license_id": license_id}


@admin_licenses_router.delete("/licenses/{license_id}")
async def delete_license(license_id: str):
    async with async_session_factory() as session:
        repo = LicenseRepository(session)
        lic = await repo.get_by_id(license_id)
        if not lic:
            raise HTTPException(status_code=404, detail="License not found")

        if lic.bound_account_id:
            raise HTTPException(
                status_code=400,
                detail=f"License is bound to account {lic.bound_account_id[:8]}... Unbind it first.",
            )

        try:
            ok = await repo.delete(license_id)
            if not ok:
                raise HTTPException(status_code=404, detail="License not found")
            await session.commit()
            return {"status": "deleted", "license_id": license_id}
        except IntegrityError:
            await session.rollback()
            raise HTTPException(
                status_code=400,
                detail="Cannot delete: license is referenced by one or more accounts. Unbind them first.",
            )
