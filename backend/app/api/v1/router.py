"""V1 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.after_sales import router as after_sales_router
from app.api.v1.admin_mini_program_config import router as admin_mini_program_config_router
from app.api.v1.admin_regions import router as admin_regions_router
from app.api.v1.admin_website_config import router as admin_website_config_router
from app.api.v1.admin_ai import router as admin_ai_router
from app.api.v1.admin_accounts import router as admin_accounts_router
from app.api.v1.admin_entitlement_transfers import router as admin_entitlement_transfers_router
from app.api.v1.admin_enterprises import router as admin_enterprises_router
from app.api.v1.admin_notifications import router as admin_notifications_router
from app.api.v1.admin_notification_receivers import router as admin_notification_receivers_router
from app.api.v1.admin_redemptions import router as admin_redemptions_router
from app.api.v1.admin_users import router as admin_users_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.cms import router as cms_router
from app.api.v1.admin_venues import router as admin_venues_router
from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bookings import router as bookings_router
from app.api.v1.dealer import router as dealer_router
from app.api.v1.dealer_auth import router as dealer_auth_router
from app.api.v1.dealer_links import router as dealer_links_router
from app.api.v1.dealer_notifications import router as dealer_notifications_router
from app.api.v1.entitlements import router as entitlements_router
from app.api.v1.health import router as health_router
from app.api.v1.legal import router as legal_router
from app.api.v1.mini_program_auth import router as mini_program_auth_router
from app.api.v1.mini_program_config import router as mini_program_config_router
from app.api.v1.regions import router as regions_router
from app.api.v1.h5_config import router as h5_config_router
from app.api.v1.website_config import router as website_config_router
from app.api.v1.admin_dashboard import router as admin_dashboard_router
from app.api.v1.admin_dev import router as admin_dev_router
from app.api.v1.admin_legal import router as admin_legal_router
from app.api.v1.admin_service_categories import router as admin_service_categories_router
from app.api.v1.orders import router as orders_router
from app.api.v1.openapi_proxy import router as openapi_proxy_router
from app.api.v1.payments import router as payments_router
from app.api.v1.cart import router as cart_router
from app.api.v1.product_categories import router as product_categories_router
from app.api.v1.products import router as products_router
from app.api.v1.provider_auth import router as provider_auth_router
from app.api.v1.provider import router as provider_router
from app.api.v1.provider_notifications import router as provider_notifications_router
from app.api.v1.provider_onboarding import router as provider_onboarding_router
from app.api.v1.service_packages import router as service_packages_router
from app.api.v1.service_categories import router as service_categories_router
from app.api.v1.admin_service_packages import router as admin_service_packages_router
from app.api.v1.admin_service_package_pricing import router as admin_service_package_pricing_router
from app.api.v1.admin_sellable_cards import router as admin_sellable_cards_router
from app.api.v1.admin_provider_onboarding import router as admin_provider_onboarding_router
from app.api.v1.admin_dealer_settlements import router as admin_dealer_settlements_router
from app.api.v1.admin_security import router as admin_security_router
from app.api.v1.taxonomy_nodes import router as taxonomy_nodes_router
from app.api.v1.users import router as users_router
from app.api.v1.venues import router as venues_router
from app.api.v1.sellable_cards import router as sellable_cards_router
from app.api.v1.tags import router as tags_router
from app.api.v1.admin_assets import router as admin_assets_router
from app.api.v1.dealer_sellable_cards import router as dealer_sellable_cards_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.user_addresses import router as user_addresses_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(mini_program_auth_router)
router.include_router(mini_program_config_router)
router.include_router(regions_router)
router.include_router(h5_config_router)
router.include_router(legal_router)
router.include_router(website_config_router)
router.include_router(ai_router)
router.include_router(openapi_proxy_router)
router.include_router(admin_accounts_router)
router.include_router(admin_auth_router)
router.include_router(admin_mini_program_config_router)
router.include_router(admin_regions_router)
router.include_router(admin_website_config_router)
router.include_router(admin_ai_router)
router.include_router(admin_dashboard_router)
router.include_router(admin_dev_router)
router.include_router(admin_legal_router)
router.include_router(admin_service_categories_router)
router.include_router(admin_notifications_router)
router.include_router(admin_notification_receivers_router)
router.include_router(dealer_notifications_router)
router.include_router(provider_notifications_router)
router.include_router(admin_redemptions_router)
router.include_router(admin_entitlement_transfers_router)
router.include_router(admin_enterprises_router)
router.include_router(admin_users_router)
router.include_router(admin_venues_router)
router.include_router(users_router)
router.include_router(products_router)
router.include_router(provider_auth_router)
router.include_router(provider_router)
router.include_router(provider_onboarding_router)
router.include_router(product_categories_router)
router.include_router(taxonomy_nodes_router)
router.include_router(orders_router)
router.include_router(payments_router)
router.include_router(cart_router)
router.include_router(service_packages_router)
router.include_router(service_categories_router)
router.include_router(admin_service_packages_router)
router.include_router(admin_service_package_pricing_router)
router.include_router(admin_sellable_cards_router)
router.include_router(admin_provider_onboarding_router)
router.include_router(admin_dealer_settlements_router)
router.include_router(admin_security_router)
router.include_router(entitlements_router)
router.include_router(after_sales_router)
router.include_router(cms_router)
router.include_router(audit_logs_router)
router.include_router(dealer_links_router)
router.include_router(dealer_auth_router)
router.include_router(dealer_router)
router.include_router(dealer_sellable_cards_router)
router.include_router(venues_router)
router.include_router(bookings_router)
router.include_router(sellable_cards_router)
router.include_router(tags_router)
router.include_router(admin_assets_router)
router.include_router(uploads_router)
router.include_router(user_addresses_router)
