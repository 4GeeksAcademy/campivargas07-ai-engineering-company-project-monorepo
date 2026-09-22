/**
 * telemetry.ts — Canonical Telemetry Contract Types for Brasaland Backoffice
 * Derived strictly from docs/telemetry/event-schemas.json (v1.0.0, Zero PII)
 */

export const SCHEMA_VERSION = "1.0.0" as const;

export interface TelemetryEnvelope<TEventType extends EventType, TProps> {
  eventId: string; // UUID v4
  timestamp: string; // ISO 8601 UTC
  sessionId: string | null;
  userId: string | null; // seudonimizado UUID
  event_type: TEventType;
  entity_action: EntityActionMap[TEventType];
  schemaVersion: typeof SCHEMA_VERSION;
  requestId: string;
  properties: TProps;
}

export interface InboundOrderCreatedProperties {
  order_id: string;
  local_id: string;
  ingredient_id: string;
  ingredient_sku: string;
  quantity: number;
  unit_of_measure: string;
  previous_stock: number;
  resulting_stock: number;
}

export interface OutboundOrderCreatedProperties {
  order_id: string;
  local_id: string;
  ingredient_id: string;
  ingredient_sku: string;
  quantity: number;
  unit_of_measure: string;
  previous_stock: number;
  resulting_stock: number;
}

export interface StockThresholdTriggeredProperties {
  local_id: string;
  ingredient_id: string;
  ingredient_sku: string;
  current_stock: number;
  minimum_stock: number;
  deficit: number;
  unit_of_measure: string;
  severity: 'critical_depletion' | 'minimum_reached';
}

export interface OutboundInsufficientStockAttemptedProperties {
  local_id: string;
  ingredient_id: string;
  ingredient_sku: string;
  requested_quantity: number;
  available_stock: number;
  unit_of_measure: string;
  rejection_source: 'client_form_guard' | 'backend_transaction_lock';
}

export interface DirectStockEditRejectedProperties {
  target_resource: string;
  attempted_operation: string;
  rejection_reason: string;
  local_id: string;
}

export interface InventoryCatalogViewedProperties {
  local_id: string;
  total_items_rendered: number;
  low_stock_items_count: number;
  depleted_items_count: number;
}

export interface IngredientDetailQueriedProperties {
  local_id: string;
  ingredient_id: string;
  ingredient_sku: string;
  current_stock: number;
  unit_of_measure: string;
}

export interface InventoryFilterAppliedProperties {
  local_id: string;
  category_filter: string;
  search_term_length: number;
  results_count: number;
}

export interface PurchaseOrderSuggestedProperties {
  suggestion_id: string;
  local_id: string;
  supplier_id: string;
  items_count: number;
  total_estimated_amount: number;
  currency: 'COP' | 'USD';
  trigger_reason: 'scheduled_replenishment' | 'stockout_prevention' | 'manual_generation';
}

export interface PurchaseOrderApprovedProperties {
  order_id: string;
  local_id: string;
  supplier_id: string;
  total_approved_amount: number;
  currency: 'COP' | 'USD';
  approver_role: string;
  approval_latency_seconds: number;
}

export interface PurchaseOrderDispatchedProperties {
  order_id: string;
  local_id: string;
  supplier_id: string;
  dispatch_channel: 'email' | 'edi_api' | 'portal';
  estimated_delivery_date: string;
}

export interface PurchaseOrderReceivedProperties {
  order_id: string;
  local_id: string;
  supplier_id: string;
  fulfillment_status: 'complete' | 'partial' | 'discrepant';
  lead_time_hours: number;
}

export interface PurchaseOrderRejectedProperties {
  order_id: string;
  local_id: string;
  supplier_id: string;
  rejection_reason_code: 'budget_limit_exceeded' | 'duplicate_order' | 'supplier_unavailable' | 'manual_cancellation';
}

export interface SupplierPriceVarianceDetectedProperties {
  supplier_id: string;
  ingredient_id: string;
  ingredient_sku: string;
  contracted_unit_price: number;
  invoiced_unit_price: number;
  variance_percentage: number;
  currency: 'COP' | 'USD';
}

export interface ConsolidatedProcurementReportGeneratedProperties {
  reporting_period: string;
  total_spend_cop: number;
  total_spend_usd: number;
  total_orders_count: number;
  active_suppliers_count: number;
}

export interface DailySalesRecordedProperties {
  local_id: string;
  business_date: string;
  total_sales_amount: number;
  currency: 'COP' | 'USD';
  total_covers: number;
  average_ticket: number;
  lines_count: number;
}

export interface PosOrderCompletedProperties {
  local_id: string;
  order_id: string;
  total_amount: number;
  currency: 'COP' | 'USD';
  covers: number;
  items_count: number;
}

export interface LocationZeroSalesAlertTriggeredProperties {
  local_id: string;
  operating_minutes_without_sales: number;
  operating_hour: number;
  expected_minimum_covers: number;
}

export interface PosHeartbeatRecordedProperties {
  local_id: string;
  terminal_id: string;
  connectivity_status: 'online' | 'degraded' | 'offline_sync';
}

export interface UserLoggedInProperties {
  auth_provider: 'local_password' | 'jwt_refresh';
  user_role: string;
  assigned_local_id: string;
}

export interface UserLoginFailedProperties {
  failure_reason: 'invalid_credentials' | 'account_locked' | 'inactive_user' | 'rate_limited';
  attempt_counter: number;
}

export interface SessionExpiredProperties {
  expiry_reason: 'token_jwt_expired' | 'idle_timeout' | 'forced_logout';
  session_duration_seconds: number;
}

export interface PermissionDeniedProperties {
  required_role: string;
  user_role: string;
  target_endpoint: string;
  http_method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
}

export interface PasswordResetRequestedProperties {
  delivery_channel: 'email';
  request_outcome: 'dispatched' | 'suppressed_unknown_account';
}

export interface ApiLatencyRecordedProperties {
  route_path: string;
  http_method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  status_code: number;
  duration_ms: number;
  db_query_count: number;
}

export interface ClientWebVitalsRecordedProperties {
  page_route: string;
  metric_name: 'LCP' | 'FID' | 'CLS' | 'INP' | 'TTFB';
  metric_value: number;
  rating: 'good' | 'needs_improvement' | 'poor';
}

export interface DbQuerySlowDetectedProperties {
  query_type: 'SELECT' | 'INSERT' | 'UPDATE' | 'DELETE' | 'AGGREGATE';
  table_name: string;
  execution_time_ms: number;
  threshold_ms: number;
}

export interface FormValidationFailedProperties {
  form_id: 'inbound_order_form' | 'outbound_order_form' | 'ingredient_create_form' | 'supplier_form';
  field_name: string;
  error_rule: string;
}

export interface SystemExceptionCapturedProperties {
  exception_class: string;
  error_code: string;
  origin_service: string;
}

export interface ExternalIntegrationFailedProperties {
  integration_target: 'resend_email' | 'pos_gateway' | 'whatsapp_api';
  error_code: string;
  retry_attempt: number;
}

export interface BackofficePageViewedProperties {
  previous_route: string;
  current_route: string;
  navigation_duration_ms: number;
}

export interface FormAbandonedProperties {
  form_id: 'inbound_order_form' | 'outbound_order_form' | 'ingredient_create_form';
  fields_filled_count: number;
  time_spent_seconds: number;
}

export type EventType =
  | 'inbound_order_created'
  | 'outbound_order_created'
  | 'stock_threshold_triggered'
  | 'outbound_insufficient_stock_attempted'
  | 'direct_stock_edit_rejected'
  | 'inventory_catalog_viewed'
  | 'ingredient_detail_queried'
  | 'inventory_filter_applied'
  | 'purchase_order_suggested'
  | 'purchase_order_approved'
  | 'purchase_order_dispatched'
  | 'purchase_order_received'
  | 'purchase_order_rejected'
  | 'supplier_price_variance_detected'
  | 'consolidated_procurement_report_generated'
  | 'daily_sales_recorded'
  | 'pos_order_completed'
  | 'location_zero_sales_alert_triggered'
  | 'pos_heartbeat_recorded'
  | 'user_logged_in'
  | 'user_login_failed'
  | 'session_expired'
  | 'permission_denied'
  | 'password_reset_requested'
  | 'api_latency_recorded'
  | 'client_web_vitals_recorded'
  | 'db_query_slow_detected'
  | 'form_validation_failed'
  | 'system_exception_captured'
  | 'external_integration_failed'
  | 'backoffice_page_viewed'
  | 'form_abandoned';

export interface EntityActionMap {
  'inbound_order_created': 'created';
  'outbound_order_created': 'created';
  'stock_threshold_triggered': 'triggered';
  'outbound_insufficient_stock_attempted': 'attempted';
  'direct_stock_edit_rejected': 'rejected';
  'inventory_catalog_viewed': 'viewed';
  'ingredient_detail_queried': 'queried';
  'inventory_filter_applied': 'applied';
  'purchase_order_suggested': 'suggested';
  'purchase_order_approved': 'approved';
  'purchase_order_dispatched': 'dispatched';
  'purchase_order_received': 'received';
  'purchase_order_rejected': 'rejected';
  'supplier_price_variance_detected': 'detected';
  'consolidated_procurement_report_generated': 'generated';
  'daily_sales_recorded': 'recorded';
  'pos_order_completed': 'recorded';
  'location_zero_sales_alert_triggered': 'triggered';
  'pos_heartbeat_recorded': 'recorded';
  'user_logged_in': 'logged_in';
  'user_login_failed': 'failed';
  'session_expired': 'expired';
  'permission_denied': 'denied';
  'password_reset_requested': 'requested';
  'api_latency_recorded': 'recorded';
  'client_web_vitals_recorded': 'recorded';
  'db_query_slow_detected': 'detected';
  'form_validation_failed': 'failed';
  'system_exception_captured': 'captured';
  'external_integration_failed': 'failed';
  'backoffice_page_viewed': 'viewed';
  'form_abandoned': 'abandoned';
}

export interface EventPropertiesMap {
  'inbound_order_created': InboundOrderCreatedProperties;
  'outbound_order_created': OutboundOrderCreatedProperties;
  'stock_threshold_triggered': StockThresholdTriggeredProperties;
  'outbound_insufficient_stock_attempted': OutboundInsufficientStockAttemptedProperties;
  'direct_stock_edit_rejected': DirectStockEditRejectedProperties;
  'inventory_catalog_viewed': InventoryCatalogViewedProperties;
  'ingredient_detail_queried': IngredientDetailQueriedProperties;
  'inventory_filter_applied': InventoryFilterAppliedProperties;
  'purchase_order_suggested': PurchaseOrderSuggestedProperties;
  'purchase_order_approved': PurchaseOrderApprovedProperties;
  'purchase_order_dispatched': PurchaseOrderDispatchedProperties;
  'purchase_order_received': PurchaseOrderReceivedProperties;
  'purchase_order_rejected': PurchaseOrderRejectedProperties;
  'supplier_price_variance_detected': SupplierPriceVarianceDetectedProperties;
  'consolidated_procurement_report_generated': ConsolidatedProcurementReportGeneratedProperties;
  'daily_sales_recorded': DailySalesRecordedProperties;
  'pos_order_completed': PosOrderCompletedProperties;
  'location_zero_sales_alert_triggered': LocationZeroSalesAlertTriggeredProperties;
  'pos_heartbeat_recorded': PosHeartbeatRecordedProperties;
  'user_logged_in': UserLoggedInProperties;
  'user_login_failed': UserLoginFailedProperties;
  'session_expired': SessionExpiredProperties;
  'permission_denied': PermissionDeniedProperties;
  'password_reset_requested': PasswordResetRequestedProperties;
  'api_latency_recorded': ApiLatencyRecordedProperties;
  'client_web_vitals_recorded': ClientWebVitalsRecordedProperties;
  'db_query_slow_detected': DbQuerySlowDetectedProperties;
  'form_validation_failed': FormValidationFailedProperties;
  'system_exception_captured': SystemExceptionCapturedProperties;
  'external_integration_failed': ExternalIntegrationFailedProperties;
  'backoffice_page_viewed': BackofficePageViewedProperties;
  'form_abandoned': FormAbandonedProperties;
}

export const EVENT_ACTION_MAPPING: EntityActionMap = {
  'inbound_order_created': 'created',
  'outbound_order_created': 'created',
  'stock_threshold_triggered': 'triggered',
  'outbound_insufficient_stock_attempted': 'attempted',
  'direct_stock_edit_rejected': 'rejected',
  'inventory_catalog_viewed': 'viewed',
  'ingredient_detail_queried': 'queried',
  'inventory_filter_applied': 'applied',
  'purchase_order_suggested': 'suggested',
  'purchase_order_approved': 'approved',
  'purchase_order_dispatched': 'dispatched',
  'purchase_order_received': 'received',
  'purchase_order_rejected': 'rejected',
  'supplier_price_variance_detected': 'detected',
  'consolidated_procurement_report_generated': 'generated',
  'daily_sales_recorded': 'recorded',
  'pos_order_completed': 'recorded',
  'location_zero_sales_alert_triggered': 'triggered',
  'pos_heartbeat_recorded': 'recorded',
  'user_logged_in': 'logged_in',
  'user_login_failed': 'failed',
  'session_expired': 'expired',
  'permission_denied': 'denied',
  'password_reset_requested': 'requested',
  'api_latency_recorded': 'recorded',
  'client_web_vitals_recorded': 'recorded',
  'db_query_slow_detected': 'detected',
  'form_validation_failed': 'failed',
  'system_exception_captured': 'captured',
  'external_integration_failed': 'failed',
  'backoffice_page_viewed': 'viewed',
  'form_abandoned': 'abandoned',
};

export const EVENT_ALLOWLISTS: Record<EventType, readonly string[]> = {
  'inbound_order_created': ['order_id', 'local_id', 'ingredient_id', 'ingredient_sku', 'quantity', 'unit_of_measure', 'previous_stock', 'resulting_stock'],
  'outbound_order_created': ['order_id', 'local_id', 'ingredient_id', 'ingredient_sku', 'quantity', 'unit_of_measure', 'previous_stock', 'resulting_stock'],
  'stock_threshold_triggered': ['local_id', 'ingredient_id', 'ingredient_sku', 'current_stock', 'minimum_stock', 'deficit', 'unit_of_measure', 'severity'],
  'outbound_insufficient_stock_attempted': ['local_id', 'ingredient_id', 'ingredient_sku', 'requested_quantity', 'available_stock', 'unit_of_measure', 'rejection_source'],
  'direct_stock_edit_rejected': ['target_resource', 'attempted_operation', 'rejection_reason', 'local_id'],
  'inventory_catalog_viewed': ['local_id', 'total_items_rendered', 'low_stock_items_count', 'depleted_items_count'],
  'ingredient_detail_queried': ['local_id', 'ingredient_id', 'ingredient_sku', 'current_stock', 'unit_of_measure'],
  'inventory_filter_applied': ['local_id', 'category_filter', 'search_term_length', 'results_count'],
  'purchase_order_suggested': ['suggestion_id', 'local_id', 'supplier_id', 'items_count', 'total_estimated_amount', 'currency', 'trigger_reason'],
  'purchase_order_approved': ['order_id', 'local_id', 'supplier_id', 'total_approved_amount', 'currency', 'approver_role', 'approval_latency_seconds'],
  'purchase_order_dispatched': ['order_id', 'local_id', 'supplier_id', 'dispatch_channel', 'estimated_delivery_date'],
  'purchase_order_received': ['order_id', 'local_id', 'supplier_id', 'fulfillment_status', 'lead_time_hours'],
  'purchase_order_rejected': ['order_id', 'local_id', 'supplier_id', 'rejection_reason_code'],
  'supplier_price_variance_detected': ['supplier_id', 'ingredient_id', 'ingredient_sku', 'contracted_unit_price', 'invoiced_unit_price', 'variance_percentage', 'currency'],
  'consolidated_procurement_report_generated': ['reporting_period', 'total_spend_cop', 'total_spend_usd', 'total_orders_count', 'active_suppliers_count'],
  'daily_sales_recorded': ['local_id', 'business_date', 'total_sales_amount', 'currency', 'total_covers', 'average_ticket', 'lines_count'],
  'pos_order_completed': ['local_id', 'order_id', 'total_amount', 'currency', 'covers', 'items_count'],
  'location_zero_sales_alert_triggered': ['local_id', 'operating_minutes_without_sales', 'operating_hour', 'expected_minimum_covers'],
  'pos_heartbeat_recorded': ['local_id', 'terminal_id', 'connectivity_status'],
  'user_logged_in': ['auth_provider', 'user_role', 'assigned_local_id'],
  'user_login_failed': ['failure_reason', 'attempt_counter'],
  'session_expired': ['expiry_reason', 'session_duration_seconds'],
  'permission_denied': ['required_role', 'user_role', 'target_endpoint', 'http_method'],
  'password_reset_requested': ['delivery_channel', 'request_outcome'],
  'api_latency_recorded': ['route_path', 'http_method', 'status_code', 'duration_ms', 'db_query_count'],
  'client_web_vitals_recorded': ['page_route', 'metric_name', 'metric_value', 'rating'],
  'db_query_slow_detected': ['query_type', 'table_name', 'execution_time_ms', 'threshold_ms'],
  'form_validation_failed': ['form_id', 'field_name', 'error_rule'],
  'system_exception_captured': ['exception_class', 'error_code', 'origin_service'],
  'external_integration_failed': ['integration_target', 'error_code', 'retry_attempt'],
  'backoffice_page_viewed': ['previous_route', 'current_route', 'navigation_duration_ms'],
  'form_abandoned': ['form_id', 'fields_filled_count', 'time_spent_seconds'],
};

export type AnyTelemetryEnvelope = {
  [K in EventType]: TelemetryEnvelope<K, EventPropertiesMap[K]>;
}[EventType];
