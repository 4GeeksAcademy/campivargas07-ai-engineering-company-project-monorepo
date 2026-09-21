/**
 * suppliers-api.ts — Brasaland · Supplier directory API client
 */

import { authApi } from "./auth";

export type Supplier = {
  id: string;
  nombre: string;
  pais: string;
  contactoNombre: string;
  contactoEmail: string;
  contactoTelefono: string;
  categoriasQueProvee: string[];
  tiempoEntregaDias: number;
  montoMinimoOrden: number;
  moneda: string;
  status: "activo" | "suspendido";
  updated_at: string | null;
};

export type SupplierListResponse = {
  suppliers: Supplier[];
  total: number;
};

export type SupplierCreatePayload = Omit<Supplier, "id" | "updated_at">;

function getBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SUPPLIERS_API_BASE_URL;
  if (configured?.trim()) {
    return configured.trim().replace(/\/+$/, "");
  }

  // In the browser, Next.js proxies /api/* to the backend container. The
  // supplier router is itself mounted at /api/suppliers, hence /api/api/*.
  return typeof window !== "undefined" ? "/api" : "http://localhost:8000";
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = authApi.getToken();
  const response = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
  });

  if (response.status === 401) {
    authApi.logout();
    throw new Error("La sesión expiró. Inicia sesión nuevamente.");
  }

  if (!response.ok) {
    const fallbackMessage = `API error (${response.status})`;
    if (response.headers.get("content-type")?.includes("application/json")) {
      const payload = (await response.json()) as { detail?: string };
      throw new Error(payload.detail || fallbackMessage);
    }
    throw new Error(fallbackMessage);
  }

  return response.json() as Promise<T>;
}

export async function listSuppliers(
  country?: string,
  category?: string
): Promise<SupplierListResponse> {
  const params = new URLSearchParams();
  if (country) params.set("country", country);
  if (category) params.set("category", category);
  const qs = params.toString();
  return apiFetch<SupplierListResponse>(
    `/api/suppliers${qs ? `?${qs}` : ""}`
  );
}

export async function createSupplier(
  data: SupplierCreatePayload
): Promise<Supplier> {
  return apiFetch<Supplier>("/api/suppliers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateSupplierRate(
  id: string,
  montoMinimoOrden: number
): Promise<Supplier> {
  return apiFetch<Supplier>(`/api/suppliers/${id}/rate`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ montoMinimoOrden }),
  });
}

export async function updateSupplierStatus(
  id: string,
  status: "activo" | "suspendido"
): Promise<Supplier> {
  return apiFetch<Supplier>(`/api/suppliers/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function deleteSupplier(id: string): Promise<void> {
  await apiFetch<{ detail: string }>(`/api/suppliers/${id}`, {
    method: "DELETE",
  });
}
