/**
 * inventory.ts — Centralized Inventory API client for Brasaland Backoffice
 *
 * Consumes the inventory domain API from services/api (/inventory)
 */

import { authApi } from "./auth";
import { telemetryService } from "@/services/telemetry";

export interface Ingredient {
  id: string; // UUID
  sku: string;
  name: string;
  category: "carne" | "verdura" | "salsa" | "bebida" | "empaque" | "limpieza" | string;
  unit_of_measure: string;
  minimum_stock: number;
  perishable: boolean;
  created_at: string; // ISO 8601
}

export interface IngredientWithStock extends Ingredient {
  local_id: string;
  current_stock: number;
}

export interface IngredientCreateInput {
  sku: string;
  name: string;
  category: "carne" | "verdura" | "salsa" | "bebida" | "empaque" | "limpieza";
  unit_of_measure: string;
  minimum_stock: number;
  perishable: boolean;
}

export interface InboundOrderInput {
  ingredient_id: string; // UUID
  local_id: string;      // e.g. "MED-001"
  quantity: number;      // strictly > 0
}

export interface OutboundOrderInput {
  ingredient_id: string; // UUID
  local_id: string;      // e.g. "MED-001"
  quantity: number;      // strictly > 0
}

export interface InventoryOrder {
  id: string; // UUID
  type: "inbound" | "outbound";
  ingredient_id: string; // UUID
  ingredient_sku: string;
  ingredient_name: string;
  local_id: string;
  quantity: number;
  user_uuid: string; // UUID
  created_at: string; // ISO 8601
}

export interface OrderListResponse {
  orders: InventoryOrder[];
  total: number;
}

export interface OrderFilters {
  local_id?: string;
  ingredient_id?: string;
  type?: "inbound" | "outbound";
}

export class InventoryApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "InventoryApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class InventoryApiClient {
  getBaseUrl(): string {
    const envUrl = process.env.NEXT_PUBLIC_INVENTORY_API_URL;
    if (envUrl && envUrl.trim().length > 0) {
      return envUrl.trim().replace(/\/+$/, "");
    }
    return typeof window !== "undefined" ? "/api" : "http://localhost:8000";
  }

  buildUrl(endpoint: string): string {
    const baseUrl = this.getBaseUrl();
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    return `${baseUrl}${cleanEndpoint}`;
  }

  private getToken(): string | null {
    return authApi.getToken();
  }

  private getHeaders(): HeadersInit {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = this.buildUrl(endpoint);

    const headers = {
      ...this.getHeaders(),
      ...(options.headers || {}),
    };

    const startTime = typeof performance !== "undefined" ? performance.now() : Date.now();
    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
      });
    } catch (err) {
      throw new InventoryApiError(
        0,
        `No fue posible conectar con el servicio de inventario: ${err instanceof Error ? err.message : "Error de red"}`
      );
    }

    const durationMs = typeof performance !== "undefined" ? Math.max(0, performance.now() - startTime) : 0;
    const httpMethod = ((options.method || "GET").toUpperCase()) as "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    const cleanPath = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const normalizedRoute = cleanPath.replace(
      /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i,
      "{id}"
    );

    if (!url.includes("/telemetry/events")) {
      try {
        telemetryService.track("api_latency_recorded", {
          route_path: normalizedRoute,
          http_method: httpMethod,
          status_code: response.status,
          duration_ms: Math.round(durationMs * 100) / 100,
          db_query_count: 0,
        });
      } catch {
        // Telemetry must never crash or block business operations
      }
    }

    if (response.status === 401) {
      if (typeof window !== "undefined") {
        authApi.logout();
      }
      throw new InventoryApiError(401, "Sesión expirada o no autorizada. Redirigiendo al login...");
    }

    if (!response.ok) {
      let detailMessage = `Error en la solicitud HTTP ${response.status}`;
      try {
        const text = await response.text();
        if (text) {
          try {
            const errJson = JSON.parse(text);
            if (typeof errJson?.detail === "string") {
              detailMessage = errJson.detail;
            } else if (Array.isArray(errJson?.detail)) {
              // FastAPI / Pydantic validation error list
              detailMessage = errJson.detail
                .map((item: { msg?: string; loc?: (string | number)[] }) => {
                  const field = item.loc && item.loc.length > 0 ? item.loc[item.loc.length - 1] : "";
                  return field ? `${field}: ${item.msg}` : (item.msg || "Validación fallida");
                })
                .join("; ");
            } else if (errJson?.message) {
              detailMessage = String(errJson.message);
            }
          } catch {
            detailMessage = text.length < 200 ? text : `Error en la solicitud HTTP ${response.status}`;
          }
        }
      } catch {
        // Fallback to generic status message
      }
      throw new InventoryApiError(response.status, detailMessage);
    }

    const responseText = await response.text();
    if (!responseText) {
      return {} as T;
    }
    try {
      return JSON.parse(responseText) as T;
    } catch {
      return responseText as unknown as T;
    }
  }

  /**
   * List ingredients with calculated stock for a mandatory restaurant ID
   */
  async listProducts(localId: string): Promise<IngredientWithStock[]> {
    if (!localId || !localId.trim()) {
      throw new InventoryApiError(422, "El identificador de local (local_id) es obligatorio");
    }
    const query = new URLSearchParams({ local_id: localId.trim() });
    return this.request<IngredientWithStock[]>(`/inventory/products?${query.toString()}`);
  }

  /**
   * Get single ingredient with calculated stock for a mandatory restaurant ID
   */
  async getProduct(productId: string, localId: string): Promise<IngredientWithStock> {
    if (!productId) {
      throw new InventoryApiError(422, "El ID del ingrediente es obligatorio");
    }
    if (!localId || !localId.trim()) {
      throw new InventoryApiError(422, "El identificador de local (local_id) es obligatorio");
    }
    const query = new URLSearchParams({ local_id: localId.trim() });
    return this.request<IngredientWithStock>(`/inventory/products/${encodeURIComponent(productId)}?${query.toString()}`);
  }

  /**
   * Create a new ingredient in the central catalog
   */
  async createProduct(data: IngredientCreateInput): Promise<Ingredient> {
    return this.request<Ingredient>("/inventory/products", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /**
   * Record an inbound order (stock receipt)
   */
  async createInboundOrder(data: InboundOrderInput): Promise<InventoryOrder> {
    if (isNaN(data.quantity) || data.quantity <= 0) {
      throw new InventoryApiError(422, "La cantidad de entrada debe ser mayor a 0");
    }
    return this.request<InventoryOrder>("/inventory/orders/inbound", {
      method: "POST",
      body: JSON.stringify({
        ingredient_id: data.ingredient_id,
        local_id: data.local_id,
        quantity: Number(data.quantity),
      }),
    });
  }

  /**
   * Record an outbound order (stock consumption)
   */
  async createOutboundOrder(data: OutboundOrderInput): Promise<InventoryOrder> {
    if (isNaN(data.quantity) || data.quantity <= 0) {
      throw new InventoryApiError(422, "La cantidad de salida debe ser mayor a 0");
    }
    return this.request<InventoryOrder>("/inventory/orders/outbound", {
      method: "POST",
      body: JSON.stringify({
        ingredient_id: data.ingredient_id,
        local_id: data.local_id,
        quantity: Number(data.quantity),
      }),
    });
  }

  /**
   * List inventory orders with joined ingredient details
   */
  async listOrders(filters?: OrderFilters): Promise<OrderListResponse> {
    const params = new URLSearchParams();
    if (filters?.local_id && filters.local_id !== "ALL") {
      params.append("local_id", filters.local_id);
    }
    if (filters?.ingredient_id) {
      params.append("ingredient_id", filters.ingredient_id);
    }
    if (filters?.type) {
      params.append("type", filters.type);
    }

    const qs = params.toString();
    const endpoint = qs ? `/inventory/orders?${qs}` : "/inventory/orders";
    return this.request<OrderListResponse>(endpoint);
  }
}

export const inventoryApi = new InventoryApiClient();
