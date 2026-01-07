"""枚举定义（v1 最小集合）。

说明：仅收敛“规格已明确”的枚举，避免提前引入未定义口径。
"""

from __future__ import annotations

from enum import StrEnum


class UserIdentity(StrEnum):
    """用户身份（可叠加）。"""

    MEMBER = "MEMBER"
    EMPLOYEE = "EMPLOYEE"


class EnterpriseSource(StrEnum):
    """企业信息库录入来源。

    规格来源：prototypes/admin.md -> 企业信息库（来源筛选）
    """

    USER_FIRST_BINDING = "USER_FIRST_BINDING"  # 用户首次绑定
    IMPORT = "IMPORT"  # 导入
    MANUAL = "MANUAL"  # 手工


class UserEnterpriseBindingStatus(StrEnum):
    """用户企业绑定关系状态。

    规格来源：
    - design.md -> 附录 B1（状态与迁移）
    - prototypes/admin.md -> 绑定关系列表状态列
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProductFulfillmentType(StrEnum):
    """商品履约类型（v2：到店服务 + 物流商品）。"""

    SERVICE = "SERVICE"
    PHYSICAL_GOODS = "PHYSICAL_GOODS"


class OrderFulfillmentStatus(StrEnum):
    """物流履约状态（仅用于 PHYSICAL_GOODS）。"""

    NOT_SHIPPED = "NOT_SHIPPED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    RECEIVED = "RECEIVED"


class ProductStatus(StrEnum):
    """商品状态（v1 最小可执行）。"""

    PENDING_REVIEW = "PENDING_REVIEW"
    ON_SALE = "ON_SALE"
    OFF_SHELF = "OFF_SHELF"
    REJECTED = "REJECTED"


class CommonEnabledStatus(StrEnum):
    """启用/停用（分类/节点等通用）。"""

    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class TaxonomyType(StrEnum):
    """分类体系节点类型。"""

    VENUE = "VENUE"
    PRODUCT = "PRODUCT"
    CONTENT = "CONTENT"
    PRODUCT_TAG = "PRODUCT_TAG"
    SERVICE_TAG = "SERVICE_TAG"
    VENUE_TAG = "VENUE_TAG"


class OrderType(StrEnum):
    """订单类型（v1 最小可执行）。"""

    PRODUCT = "PRODUCT"
    SERVICE_PACKAGE = "SERVICE_PACKAGE"


class OrderItemType(StrEnum):
    """订单明细类型。"""

    PRODUCT = "PRODUCT"
    SERVICE_PACKAGE = "SERVICE_PACKAGE"


class PaymentMethod(StrEnum):
    """支付方式（v1 最小可执行）。"""

    WECHAT = "WECHAT"
    ALIPAY = "ALIPAY"
    BANK_TRANSFER = "BANK_TRANSFER"


class PaymentStatus(StrEnum):
    """支付状态（与 orders.paymentStatus 对齐）。"""

    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class CardStatus(StrEnum):
    """购卡实例绑定状态（H5 匿名购卡 -> 小程序绑定，v1）。"""

    UNBOUND = "UNBOUND"
    BOUND = "BOUND"


class AfterSaleType(StrEnum):
    """售后类型（v1 最小可执行）。"""

    RETURN = "RETURN"
    REFUND = "REFUND"
    AFTER_SALE_SERVICE = "AFTER_SALE_SERVICE"


class AfterSaleStatus(StrEnum):
    """售后状态流转（v1 最小可执行）。"""

    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    DECIDED = "DECIDED"
    CLOSED = "CLOSED"


class AfterSaleDecision(StrEnum):
    """售后裁决（v1：不支持 PARTIAL）。"""

    APPROVE = "APPROVE"
    REJECT = "REJECT"


class RefundStatus(StrEnum):
    """退款状态（v1 最小可执行）。"""

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ServicePackageInstanceStatus(StrEnum):
    """高端服务卡实例状态（v1 最小）。"""

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    TRANSFERRED = "TRANSFERRED"
    REFUNDED = "REFUNDED"


class EntitlementType(StrEnum):
    """权益类型。"""

    SERVICE_PACKAGE = "SERVICE_PACKAGE"


class EntitlementStatus(StrEnum):
    """权益状态（v1 最小）。"""

    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    TRANSFERRED = "TRANSFERRED"
    REFUNDED = "REFUNDED"


class RedemptionMethod(StrEnum):
    """核销方式。"""

    QR_CODE = "QR_CODE"
    VOUCHER_CODE = "VOUCHER_CODE"
    BOTH = "BOTH"


class RedemptionStatus(StrEnum):
    """核销结果状态。"""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class VenuePublishStatus(StrEnum):
    """场所发布状态。"""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    OFFLINE = "OFFLINE"


class VenueReviewStatus(StrEnum):
    """场所展示资料审核状态（v1+：用于区分“草稿/待审/通过/驳回”，不等同于 publish_status）。"""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BookingStatus(StrEnum):
    """预约状态。"""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class BookingConfirmationMethod(StrEnum):
    """预约确认方式。"""

    AUTO = "AUTO"
    MANUAL = "MANUAL"


class BookingSourceType(StrEnum):
    """预约来源类型（vNow：支持权益预约 + 基建联防服务商品订单预约）。"""

    ENTITLEMENT = "ENTITLEMENT"
    ORDER_ITEM = "ORDER_ITEM"


class DealerStatus(StrEnum):
    """经销商状态（v1）。"""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class DealerLinkStatus(StrEnum):
    """经销商链接状态。"""

    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    EXPIRED = "EXPIRED"


class ProviderInfraCommerceStatus(StrEnum):
    """服务提供方：基建联防开通状态（v1）。"""

    NOT_OPENED = "NOT_OPENED"
    OPENED = "OPENED"


class ProviderHealthCardStatus(StrEnum):
    """服务提供方：健行天下供给开通状态（v1）。"""

    NOT_APPLIED = "NOT_APPLIED"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SettlementStatus(StrEnum):
    """结算状态。"""

    PENDING_CONFIRM = "PENDING_CONFIRM"
    SETTLED = "SETTLED"
    FROZEN = "FROZEN"


class NotificationReceiverType(StrEnum):
    """通知接收者类型。"""

    ADMIN = "ADMIN"
    USER = "USER"
    DEALER = "DEALER"
    PROVIDER = "PROVIDER"
    PROVIDER_STAFF = "PROVIDER_STAFF"


class NotificationStatus(StrEnum):
    """通知状态。"""

    UNREAD = "UNREAD"
    READ = "READ"


class NotificationCategory(StrEnum):
    """通知类别（用于接收端展示/筛选，v1 最小）。"""

    SYSTEM = "SYSTEM"
    ACTIVITY = "ACTIVITY"
    OPS = "OPS"


class AuditActorType(StrEnum):
    """审计操作者类型。"""

    ADMIN = "ADMIN"
    USER = "USER"
    DEALER = "DEALER"
    PROVIDER = "PROVIDER"
    PROVIDER_STAFF = "PROVIDER_STAFF"


class AuditAction(StrEnum):
    """审计动作类型。"""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    PUBLISH = "PUBLISH"
    OFFLINE = "OFFLINE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


class CmsContentStatus(StrEnum):
    """CMS 内容状态。"""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    OFFLINE = "OFFLINE"


class LegalAgreementStatus(StrEnum):
    """协议/条款状态（v1 最小）。"""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    OFFLINE = "OFFLINE"
