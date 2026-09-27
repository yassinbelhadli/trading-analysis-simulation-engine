from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database.db import async_session_factory
from database.repositories.user_repository import UserRepository

admin_users_router = APIRouter()


class UpdateUserRequest(BaseModel):
    status: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None


@admin_users_router.get("/users")
async def list_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
):
    async with async_session_factory() as session:
        repo = UserRepository(session)
        from sqlalchemy import select
        from database.models import User
        stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        if status:
            stmt = stmt.where(User.status == status)
        result = await session.execute(stmt)
        users = list(result.scalars().all())
        return [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "telegram_username": u.telegram_username,
                "first_name": u.first_name,
                "language": u.language,
                "status": u.status,
                "created_at": u.created_at.isoformat(),
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ]


@admin_users_router.get("/users/{user_id}")
async def get_user(user_id: str):
    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language": user.language,
            "timezone": user.timezone,
            "status": user.status,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "licenses_count": len(user.licenses) if user.licenses else 0,
            "accounts_count": len(user.accounts) if user.accounts else 0,
        }


@admin_users_router.patch("/users/{user_id}")
async def update_user(user_id: str, body: UpdateUserRequest):
    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        changed = False
        if body.status is not None and body.status != user.status:
            user.status = body.status
            changed = True
        if body.language is not None and body.language != user.language:
            user.language = body.language
            changed = True
        if body.timezone is not None and body.timezone != user.timezone:
            user.timezone = body.timezone
            changed = True
        if changed:
            await session.commit()
        return {"status": "updated", "user_id": user_id}
