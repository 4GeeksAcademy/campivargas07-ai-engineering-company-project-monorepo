"""Telemetry domain Pydantic schemas generated from docs/telemetry/event-schemas.json."""
from datetime import date, datetime
from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Base Envelope
class TelemetryEnvelopeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eventId: UUID
    timestamp: datetime
    sessionId: Optional[str] = None
    userId: Optional[UUID] = None
    schemaVersion: Literal["1.0.0"] = "1.0.0"
    requestId: str = Field(..., min_length=1)

class InboundOrderCreatedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    local_id: str = Field(..., min_length=1)
    ingredient_id: UUID
    ingredient_sku: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unit_of_measure: str = Field(..., min_length=1)
    previous_stock: float
    resulting_stock: float

class InboundOrderCreatedEvent(TelemetryEnvelopeBase):
    event_type: Literal["inbound_order_created"] = "inbound_order_created"
    entity_action: Literal["created"] = "created"
    properties: InboundOrderCreatedProperties

class OutboundOrderCreatedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    local_id: str = Field(..., min_length=1)
    ingredient_id: UUID
    ingredient_sku: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unit_of_measure: str = Field(..., min_length=1)
    previous_stock: float
    resulting_stock: float = Field(..., ge=0)

class OutboundOrderCreatedEvent(TelemetryEnvelopeBase):
    event_type: Literal["outbound_order_created"] = "outbound_order_created"
    entity_action: Literal["created"] = "created"
    properties: OutboundOrderCreatedProperties

class StockThresholdTriggeredProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    ingredient_id: UUID
    ingredient_sku: str = Field(..., min_length=1)
    current_stock: float
    minimum_stock: float = Field(..., ge=0)
    deficit: float = Field(..., ge=0)
    unit_of_measure: str = Field(..., min_length=1)
    severity: Literal["critical_depletion", "minimum_reached"]

class StockThresholdTriggeredEvent(TelemetryEnvelopeBase):
    event_type: Literal["stock_threshold_triggered"] = "stock_threshold_triggered"
    entity_action: Literal["triggered"] = "triggered"
    properties: StockThresholdTriggeredProperties

class OutboundInsufficientStockAttemptedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    ingredient_id: UUID
    ingredient_sku: str = Field(..., min_length=1)
    requested_quantity: float = Field(..., gt=0)
    available_stock: float
    unit_of_measure: str = Field(..., min_length=1)
    rejection_source: Literal["client_form_guard", "backend_transaction_lock"]

class OutboundInsufficientStockAttemptedEvent(TelemetryEnvelopeBase):
    event_type: Literal["outbound_insufficient_stock_attempted"] = "outbound_insufficient_stock_attempted"
    entity_action: Literal["attempted"] = "attempted"
    properties: OutboundInsufficientStockAttemptedProperties

class DirectStockEditRejectedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_resource: str = Field(..., min_length=1)
    attempted_operation: str = Field(..., min_length=1)
    rejection_reason: str = Field(..., min_length=1)
    local_id: str = Field(..., min_length=1)

class DirectStockEditRejectedEvent(TelemetryEnvelopeBase):
    event_type: Literal["direct_stock_edit_rejected"] = "direct_stock_edit_rejected"
    entity_action: Literal["rejected"] = "rejected"
    properties: DirectStockEditRejectedProperties

class InventoryCatalogViewedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    total_items_rendered: int = Field(..., ge=0)
    low_stock_items_count: int = Field(..., ge=0)
    depleted_items_count: int = Field(..., ge=0)

class InventoryCatalogViewedEvent(TelemetryEnvelopeBase):
    event_type: Literal["inventory_catalog_viewed"] = "inventory_catalog_viewed"
    entity_action: Literal["viewed"] = "viewed"
    properties: InventoryCatalogViewedProperties

class IngredientDetailQueriedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    ingredient_id: UUID
    ingredient_sku: str = Field(..., min_length=1)
    current_stock: float
    unit_of_measure: str = Field(..., min_length=1)

class IngredientDetailQueriedEvent(TelemetryEnvelopeBase):
    event_type: Literal["ingredient_detail_queried"] = "ingredient_detail_queried"
    entity_action: Literal["queried"] = "queried"
    properties: IngredientDetailQueriedProperties

class InventoryFilterAppliedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    category_filter: str
    search_term_length: int = Field(..., ge=0)
    results_count: int = Field(..., ge=0)

class InventoryFilterAppliedEvent(TelemetryEnvelopeBase):
    event_type: Literal["inventory_filter_applied"] = "inventory_filter_applied"
    entity_action: Literal["applied"] = "applied"
    properties: InventoryFilterAppliedProperties

class PurchaseOrderSuggestedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggestion_id: UUID
    local_id: str = Field(..., min_length=1)
    supplier_id: str = Field(..., min_length=1)
    items_count: int = Field(..., ge=1)
    total_estimated_amount: float = Field(..., ge=0)
    currency: Literal["COP", "USD"]
    trigger_reason: Literal["scheduled_replenishment", "stockout_prevention", "manual_generation"]

class PurchaseOrderSuggestedEvent(TelemetryEnvelopeBase):
    event_type: Literal["purchase_order_suggested"] = "purchase_order_suggested"
    entity_action: Literal["suggested"] = "suggested"
    properties: PurchaseOrderSuggestedProperties

class PurchaseOrderApprovedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    local_id: str = Field(..., min_length=1)
    supplier_id: str = Field(..., min_length=1)
    total_approved_amount: float = Field(..., ge=0)
    currency: Literal["COP", "USD"]
    approver_role: str = Field(..., min_length=1)
    approval_latency_seconds: float = Field(..., ge=0)

class PurchaseOrderApprovedEvent(TelemetryEnvelopeBase):
    event_type: Literal["purchase_order_approved"] = "purchase_order_approved"
    entity_action: Literal["approved"] = "approved"
    properties: PurchaseOrderApprovedProperties

class PurchaseOrderDispatchedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    local_id: str = Field(..., min_length=1)
    supplier_id: str = Field(..., min_length=1)
    dispatch_channel: Literal["email", "edi_api", "portal"]
    estimated_delivery_date: date

class PurchaseOrderDispatchedEvent(TelemetryEnvelopeBase):
    event_type: Literal["purchase_order_dispatched"] = "purchase_order_dispatched"
    entity_action: Literal["dispatched"] = "dispatched"
    properties: PurchaseOrderDispatchedProperties

class PurchaseOrderReceivedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    local_id: str = Field(..., min_length=1)
    supplier_id: str = Field(..., min_length=1)
    fulfillment_status: Literal["complete", "partial", "discrepant"]
    lead_time_hours: float = Field(..., ge=0)

class PurchaseOrderReceivedEvent(TelemetryEnvelopeBase):
    event_type: Literal["purchase_order_received"] = "purchase_order_received"
    entity_action: Literal["received"] = "received"
    properties: PurchaseOrderReceivedProperties

class PurchaseOrderRejectedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    local_id: str = Field(..., min_length=1)
    supplier_id: str = Field(..., min_length=1)
    rejection_reason_code: Literal["budget_limit_exceeded", "duplicate_order", "supplier_unavailable", "manual_cancellation"]

class PurchaseOrderRejectedEvent(TelemetryEnvelopeBase):
    event_type: Literal["purchase_order_rejected"] = "purchase_order_rejected"
    entity_action: Literal["rejected"] = "rejected"
    properties: PurchaseOrderRejectedProperties

class SupplierPriceVarianceDetectedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: str = Field(..., min_length=1)
    ingredient_id: UUID
    ingredient_sku: str = Field(..., min_length=1)
    contracted_unit_price: float = Field(..., gt=0)
    invoiced_unit_price: float = Field(..., gt=0)
    variance_percentage: float
    currency: Literal["COP", "USD"]

class SupplierPriceVarianceDetectedEvent(TelemetryEnvelopeBase):
    event_type: Literal["supplier_price_variance_detected"] = "supplier_price_variance_detected"
    entity_action: Literal["detected"] = "detected"
    properties: SupplierPriceVarianceDetectedProperties

class ConsolidatedProcurementReportGeneratedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reporting_period: str
    total_spend_cop: float = Field(..., ge=0)
    total_spend_usd: float = Field(..., ge=0)
    total_orders_count: int = Field(..., ge=0)
    active_suppliers_count: int = Field(..., ge=0)

class ConsolidatedProcurementReportGeneratedEvent(TelemetryEnvelopeBase):
    event_type: Literal["consolidated_procurement_report_generated"] = "consolidated_procurement_report_generated"
    entity_action: Literal["generated"] = "generated"
    properties: ConsolidatedProcurementReportGeneratedProperties

class DailySalesRecordedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    business_date: date
    total_sales_amount: float = Field(..., ge=0)
    currency: Literal["COP", "USD"]
    total_covers: int = Field(..., ge=0)
    average_ticket: float = Field(..., ge=0)
    lines_count: int = Field(..., ge=0)

class DailySalesRecordedEvent(TelemetryEnvelopeBase):
    event_type: Literal["daily_sales_recorded"] = "daily_sales_recorded"
    entity_action: Literal["recorded"] = "recorded"
    properties: DailySalesRecordedProperties

class PosOrderCompletedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    order_id: str = Field(..., min_length=1)
    total_amount: float = Field(..., ge=0)
    currency: Literal["COP", "USD"]
    covers: int = Field(..., ge=1)
    items_count: int = Field(..., ge=1)

class PosOrderCompletedEvent(TelemetryEnvelopeBase):
    event_type: Literal["pos_order_completed"] = "pos_order_completed"
    entity_action: Literal["recorded"] = "recorded"
    properties: PosOrderCompletedProperties

class LocationZeroSalesAlertTriggeredProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    operating_minutes_without_sales: int = Field(..., ge=15)
    operating_hour: int = Field(..., ge=0, le=23)
    expected_minimum_covers: int = Field(..., ge=0)

class LocationZeroSalesAlertTriggeredEvent(TelemetryEnvelopeBase):
    event_type: Literal["location_zero_sales_alert_triggered"] = "location_zero_sales_alert_triggered"
    entity_action: Literal["triggered"] = "triggered"
    properties: LocationZeroSalesAlertTriggeredProperties

class PosHeartbeatRecordedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    local_id: str = Field(..., min_length=1)
    terminal_id: str = Field(..., min_length=1)
    connectivity_status: Literal["online", "degraded", "offline_sync"]

class PosHeartbeatRecordedEvent(TelemetryEnvelopeBase):
    event_type: Literal["pos_heartbeat_recorded"] = "pos_heartbeat_recorded"
    entity_action: Literal["recorded"] = "recorded"
    properties: PosHeartbeatRecordedProperties

class UserLoggedInProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auth_provider: Literal["local_password", "jwt_refresh"]
    user_role: str = Field(..., min_length=1)
    assigned_local_id: str = Field(..., min_length=1)

class UserLoggedInEvent(TelemetryEnvelopeBase):
    event_type: Literal["user_logged_in"] = "user_logged_in"
    entity_action: Literal["logged_in"] = "logged_in"
    properties: UserLoggedInProperties

class UserLoginFailedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    failure_reason: Literal["invalid_credentials", "account_locked", "inactive_user", "rate_limited"]
    attempt_counter: int = Field(..., ge=1)

class UserLoginFailedEvent(TelemetryEnvelopeBase):
    event_type: Literal["user_login_failed"] = "user_login_failed"
    entity_action: Literal["failed"] = "failed"
    properties: UserLoginFailedProperties

class SessionExpiredProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expiry_reason: Literal["token_jwt_expired", "idle_timeout", "forced_logout"]
    session_duration_seconds: int = Field(..., ge=0)

class SessionExpiredEvent(TelemetryEnvelopeBase):
    event_type: Literal["session_expired"] = "session_expired"
    entity_action: Literal["expired"] = "expired"
    properties: SessionExpiredProperties

class PermissionDeniedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_role: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    target_endpoint: str = Field(..., min_length=1)
    http_method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]

class PermissionDeniedEvent(TelemetryEnvelopeBase):
    event_type: Literal["permission_denied"] = "permission_denied"
    entity_action: Literal["denied"] = "denied"
    properties: PermissionDeniedProperties

class PasswordResetRequestedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delivery_channel: Literal["email"]
    request_outcome: Literal["dispatched", "suppressed_unknown_account"]

class PasswordResetRequestedEvent(TelemetryEnvelopeBase):
    event_type: Literal["password_reset_requested"] = "password_reset_requested"
    entity_action: Literal["requested"] = "requested"
    properties: PasswordResetRequestedProperties

class ApiLatencyRecordedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route_path: str = Field(..., min_length=1)
    http_method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    status_code: int = Field(..., ge=100, le=599)
    duration_ms: float = Field(..., ge=0)
    db_query_count: int = Field(..., ge=0)

class ApiLatencyRecordedEvent(TelemetryEnvelopeBase):
    event_type: Literal["api_latency_recorded"] = "api_latency_recorded"
    entity_action: Literal["recorded"] = "recorded"
    properties: ApiLatencyRecordedProperties

class ClientWebVitalsRecordedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_route: str = Field(..., min_length=1)
    metric_name: Literal["LCP", "FID", "CLS", "INP", "TTFB"]
    metric_value: float = Field(..., ge=0)
    rating: Literal["good", "needs_improvement", "poor"]

class ClientWebVitalsRecordedEvent(TelemetryEnvelopeBase):
    event_type: Literal["client_web_vitals_recorded"] = "client_web_vitals_recorded"
    entity_action: Literal["recorded"] = "recorded"
    properties: ClientWebVitalsRecordedProperties

class DbQuerySlowDetectedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_type: Literal["SELECT", "INSERT", "UPDATE", "DELETE", "AGGREGATE"]
    table_name: str = Field(..., min_length=1)
    execution_time_ms: float = Field(..., ge=0)
    threshold_ms: float = Field(..., ge=0)

class DbQuerySlowDetectedEvent(TelemetryEnvelopeBase):
    event_type: Literal["db_query_slow_detected"] = "db_query_slow_detected"
    entity_action: Literal["detected"] = "detected"
    properties: DbQuerySlowDetectedProperties

class FormValidationFailedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form_id: Literal["inbound_order_form", "outbound_order_form", "ingredient_create_form", "supplier_form"]
    field_name: str = Field(..., min_length=1)
    error_rule: str = Field(..., min_length=1)

class FormValidationFailedEvent(TelemetryEnvelopeBase):
    event_type: Literal["form_validation_failed"] = "form_validation_failed"
    entity_action: Literal["failed"] = "failed"
    properties: FormValidationFailedProperties

class SystemExceptionCapturedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exception_class: str = Field(..., min_length=1)
    error_code: str = Field(..., min_length=1)
    origin_service: str = Field(..., min_length=1)

class SystemExceptionCapturedEvent(TelemetryEnvelopeBase):
    event_type: Literal["system_exception_captured"] = "system_exception_captured"
    entity_action: Literal["captured"] = "captured"
    properties: SystemExceptionCapturedProperties

class ExternalIntegrationFailedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    integration_target: Literal["resend_email", "pos_gateway", "whatsapp_api"]
    error_code: str = Field(..., min_length=1)
    retry_attempt: int = Field(..., ge=0)

class ExternalIntegrationFailedEvent(TelemetryEnvelopeBase):
    event_type: Literal["external_integration_failed"] = "external_integration_failed"
    entity_action: Literal["failed"] = "failed"
    properties: ExternalIntegrationFailedProperties

class BackofficePageViewedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    previous_route: str
    current_route: str = Field(..., min_length=1)
    navigation_duration_ms: float = Field(..., ge=0)

class BackofficePageViewedEvent(TelemetryEnvelopeBase):
    event_type: Literal["backoffice_page_viewed"] = "backoffice_page_viewed"
    entity_action: Literal["viewed"] = "viewed"
    properties: BackofficePageViewedProperties

class FormAbandonedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form_id: Literal["inbound_order_form", "outbound_order_form", "ingredient_create_form"]
    fields_filled_count: int = Field(..., ge=1)
    time_spent_seconds: int = Field(..., ge=0)

class FormAbandonedEvent(TelemetryEnvelopeBase):
    event_type: Literal["form_abandoned"] = "form_abandoned"
    entity_action: Literal["abandoned"] = "abandoned"
    properties: FormAbandonedProperties

TelemetryEvent = Annotated[Union[InboundOrderCreatedEvent, OutboundOrderCreatedEvent, StockThresholdTriggeredEvent, OutboundInsufficientStockAttemptedEvent, DirectStockEditRejectedEvent, InventoryCatalogViewedEvent, IngredientDetailQueriedEvent, InventoryFilterAppliedEvent, PurchaseOrderSuggestedEvent, PurchaseOrderApprovedEvent, PurchaseOrderDispatchedEvent, PurchaseOrderReceivedEvent, PurchaseOrderRejectedEvent, SupplierPriceVarianceDetectedEvent, ConsolidatedProcurementReportGeneratedEvent, DailySalesRecordedEvent, PosOrderCompletedEvent, LocationZeroSalesAlertTriggeredEvent, PosHeartbeatRecordedEvent, UserLoggedInEvent, UserLoginFailedEvent, SessionExpiredEvent, PermissionDeniedEvent, PasswordResetRequestedEvent, ApiLatencyRecordedEvent, ClientWebVitalsRecordedEvent, DbQuerySlowDetectedEvent, FormValidationFailedEvent, SystemExceptionCapturedEvent, ExternalIntegrationFailedEvent, BackofficePageViewedEvent, FormAbandonedEvent], Field(discriminator='event_type')]

class TelemetryBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[dict[str, Any]] = Field(..., max_length=20)

# Backward-compatible alias
TelemetryBatch = TelemetryBatchRequest

class TelemetryBatchResponse(BaseModel):
    received: int
    stored: int = 0
    rejected: int = 0
