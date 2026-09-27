from __future__ import annotations

from fastapi import APIRouter

from api.routes.admin.accounts import router as accounts_router
from api.routes.admin.audit import router as audit_router
from api.routes.admin.billing import router as billing_router
from api.routes.admin.clients import router as clients_router
from api.routes.admin.coupons import router as coupons_router
from api.routes.admin.ea_builds import router as ea_builds_router
from api.routes.admin.overview import router as overview_router
from api.routes.admin.roles import router as roles_router
from api.routes.admin.system_health import router as system_health_router
from api.routes.admin.trading import router as trading_router
from api.routes.admin.licenses import router as licenses_router
from api.routes.admin.news import router as news_router
from api.routes.admin.notifications import router as notifications_router
from api.routes.admin.promotions import router as promotions_router
from api.routes.admin.tickets import router as tickets_router
from api.routes.admin.users import router as users_router
from api.routes.admin.settings import router as settings_router
from api.routes.admin.payment_configs import router as payment_configs_router

admin_router = APIRouter(prefix="/admin", tags=["admin"])
admin_router.include_router(overview_router)
admin_router.include_router(accounts_router)
admin_router.include_router(users_router)
admin_router.include_router(licenses_router)
admin_router.include_router(ea_builds_router)
admin_router.include_router(news_router)
admin_router.include_router(notifications_router)
admin_router.include_router(promotions_router)
admin_router.include_router(trading_router)
admin_router.include_router(roles_router)
admin_router.include_router(billing_router)
admin_router.include_router(coupons_router)
admin_router.include_router(clients_router)
admin_router.include_router(audit_router)
admin_router.include_router(system_health_router)
admin_router.include_router(tickets_router)
admin_router.include_router(settings_router)
admin_router.include_router(payment_configs_router)
