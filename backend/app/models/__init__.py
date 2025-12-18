"""数据模型层（SQLAlchemy ORM）。

说明：导入模型类，便于 Alembic 自动发现元数据。
"""

from app.models.after_sale_case import AfterSaleCase  # noqa: F401
from app.models.enterprise import Enterprise  # noqa: F401
from app.models.entitlement import Entitlement  # noqa: F401
from app.models.entitlement_transfer import EntitlementTransfer  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.order_item import OrderItem  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.package_service import PackageService  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.product_category import ProductCategory  # noqa: F401
from app.models.refund import Refund  # noqa: F401
from app.models.service_package import ServicePackage  # noqa: F401
from app.models.service_package_instance import ServicePackageInstance  # noqa: F401
from app.models.taxonomy_node import TaxonomyNode  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_enterprise_binding import UserEnterpriseBinding  # noqa: F401
from app.models.redemption_record import RedemptionRecord  # noqa: F401
from app.models.venue import Venue  # noqa: F401
from app.models.venue_service import VenueService  # noqa: F401
from app.models.venue_schedule import VenueSchedule  # noqa: F401
from app.models.booking import Booking  # noqa: F401
from app.models.dealer import Dealer  # noqa: F401
from app.models.dealer_hierarchy import DealerHierarchy  # noqa: F401
from app.models.dealer_link import DealerLink  # noqa: F401
from app.models.settlement_record import SettlementRecord  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.cms_channel import CmsChannel  # noqa: F401
from app.models.cms_content import CmsContent  # noqa: F401
from app.models.system_config import SystemConfig  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.provider import Provider  # noqa: F401
