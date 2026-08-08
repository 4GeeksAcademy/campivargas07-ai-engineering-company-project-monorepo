/**
 * suppliers-api.ts — Brasaland · Supplier directory API client
 */

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

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_SUPPLIERS_API_BASE_URL ||
  process.env.NEXT_PUBLIC_INCIDENTS_API_BASE_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);

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
