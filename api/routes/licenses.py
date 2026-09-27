from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.license_service import (
    LicenseAccountNotFoundError,
    LicenseAlreadyBoundError,
    LicenseExpiredError,
    LicenseInactiveError,
    LicenseInputError,
    LicenseNotFoundError,
    LicenseOwnershipError,
    LicenseService,
)
from database.db import get_session
from database.models import User
from security.auth import get_current_user

router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.get("/my")
async def get_my_licenses(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    licenses = await LicenseService(session).list_user_licenses(current_user.id)
    return {
        "items": [
            {
                "id": l.id,
                "license_key": l.license_key,
                "plan": l.plan,
                "status": l.status,
                "max_accounts": l.max_accounts,
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                "bound_account_id": l.bound_account_id,
                "bound_at": l.bound_at.isoformat() if l.bound_at else None,
                "transfer_locked": l.transfer_locked,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in licenses
        ],
        "total": len(licenses),
    }


@router.post("/bind")
async def bind_license(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        license_key = body.get("license_key", "").strip().upper()
        account_id = body.get("account_id", "").strip()
        await LicenseService(session).bind_license(
            current_user.id,
            license_key,
            account_id,
        )
    except LicenseInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LicenseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LicenseOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (LicenseInactiveError, LicenseExpiredError, LicenseAlreadyBoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LicenseAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"message": "License bound to account", "license_key": license_key, "account_id": account_id}


@router.post("/unbind")
async def unbind_my_license(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        license_key = body.get("license_key", "").strip().upper()
        await LicenseService(session).unbind_license(current_user.id, license_key)
    except LicenseInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LicenseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LicenseOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return {"message": "License unbound successfully"}
