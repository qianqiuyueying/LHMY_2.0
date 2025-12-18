"""V1 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.after_sales import router as after_sales_router
from app.api.v1.admin_mini_program_config import router as admin_mini_program_config_router
from app.api.v1.admin_ai import router as admin_ai_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.cms import router as cms_router
from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.dealer import router as dealer_router
from app.api.v1.dealer_links import router as dealer_links_router
from app.api.v1.entitlements import router as entitlements_router
from app.api.v1.health import router as health_router
from app.api.v1.mini_program_auth import router as mini_program_auth_router
from app.api.v1.mini_program_config import router as mini_program_config_router
from app.api.v1.orders import router as orders_router
from app.api.v1.product_categories import router as product_categories_router
from app.api.v1.products import router as products_router
from app.api.v1.taxonomy_nodes import router as taxonomy_nodes_router
from app.api.v1.users import router as users_router
from app.api.v1.venues import router as venues_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(mini_program_auth_router)
router.include_router(mini_program_config_router)
router.include_router(ai_router)
router.include_router(admin_auth_router)
router.include_router(admin_mini_program_config_router)
router.include_router(admin_ai_router)
router.include_router(users_router)
router.include_router(products_router)
router.include_router(product_categories_router)
router.include_router(taxonomy_nodes_router)
router.include_router(orders_router)
router.include_router(entitlements_router)
router.include_router(after_sales_router)
router.include_router(cms_router)
router.include_router(audit_logs_router)
router.include_router(dealer_links_router)
router.include_router(dealer_router)
router.include_router(venues_router)
router.include_router(bookings_router)
