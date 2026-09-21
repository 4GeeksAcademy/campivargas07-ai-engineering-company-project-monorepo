/** Brasaland incident manager and CSV analysis API client. */

import { authApi } from "./auth";
import type {
  Incident,
  IncidentCreateRequest,
  IncidentStatusUpdateRequest,
  IncidentSummary,
} from "@repo/shared-types";

export type {
  Incident,
  IncidentBranch,
  IncidentCategory,
  IncidentCreateRequest,
  IncidentOrigin,
  IncidentStatus,
  IncidentStatusUpdateRequest,
  IncidentSummary,
} from "@repo/shared-types";

export {
  BRANCH_LABELS,
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  STATUS_LABELS,
  VALID_TRANSITIONS,
} from "@repo/shared-types";

export type BreakdownItem = {
  code: string;
  label: string;
  count: number;
  percentage?: number | null;
};

export type IncidentAnalysisResponse = {
  source_file: string;
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_breakdown: BreakdownItem[];
  category_breakdown: BreakdownItem[];
  status_breakdown: BreakdownItem[];
  satisfaction: {
    scored_closed_cases: number;
    total_closed_cases: number;
    average_score: number;
    score_breakdown: BreakdownItem[];
  };
};

function getBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_INCIDENTS_API_BASE_URL;
  if (configured?.trim()) {
    return configured.trim().replace(/\/+$/, "");
  }

  return typeof window !== "undefined" ? "/api" : "http://localhost:8000";
}

function getAuthHeaders(includeJson = true): HeadersInit {
  const headers: Record<string, string> = {};
  if (includeJson) headers["Content-Type"] = "application/json";

  const token = authApi.getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    authApi.logout();
    throw new Error("La sesión expiró. Inicia sesión nuevamente.");
  }

  if (!response.ok) {
    const fallback = `Error en la solicitud (${response.status})`;
    const payload = await response.json().catch(() => null) as {
      detail?: string;
      message?: string;
    } | null;
    throw new Error(payload?.message || payload?.detail || fallback);
  }

  return response.json() as Promise<T>;
}

export async function listIncidents(filters?: {
  status?: string;
  category?: string;
  branch?: string;
}): Promise<Incident[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.branch) params.set("branch", filters.branch);
  const query = params.toString();

  const response = await fetch(
    `${getBaseUrl()}/api/incidents${query ? `?${query}` : ""}`,
    { headers: getAuthHeaders() },
  );
  return handleResponse<Incident[]>(response);
}

export async function getIncident(id: string): Promise<Incident> {
  const response = await fetch(
    `${getBaseUrl()}/api/incidents/${encodeURIComponent(id)}`,
    { headers: getAuthHeaders() },
  );
  return handleResponse<Incident>(response);
}

export async function createIncident(data: IncidentCreateRequest): Promise<Incident> {
  const response = await fetch(`${getBaseUrl()}/api/incidents`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  return handleResponse<Incident>(response);
}

export async function updateIncidentStatus(
  id: string,
  data: IncidentStatusUpdateRequest,
): Promise<Incident> {
  const response = await fetch(
    `${getBaseUrl()}/api/incidents/${encodeURIComponent(id)}/status`,
    {
      method: "PATCH",
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    },
  );
  return handleResponse<Incident>(response);
}

export async function getIncidentsSummary(): Promise<IncidentSummary> {
  const response = await fetch(`${getBaseUrl()}/api/incidents/summary`, {
    headers: getAuthHeaders(),
  });
  return handleResponse<IncidentSummary>(response);
}

export async function analyzeIncidentsFile(file: File): Promise<IncidentAnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getBaseUrl()}/api/incidents/analyze`, {
    method: "POST",
    headers: getAuthHeaders(false),
    body: formData,
  });

  if (!response.ok) {
    const fallbackMessage = `No se pudo analizar el archivo (${response.status}).`;
    if (response.headers.get("content-type")?.includes("application/json")) {
      const payload = (await response.json()) as { detail?: string };
      throw new Error(payload.detail || fallbackMessage);
    }
    throw new Error(fallbackMessage);
  }

  return response.json() as Promise<IncidentAnalysisResponse>;
}

export async function analyzeIncidentsText(
  csvText: string,
  filename = "pasted.csv",
): Promise<IncidentAnalysisResponse> {
  const blob = new Blob([csvText], { type: "text/csv" });
  const file = new File([blob], filename, { type: "text/csv" });
  return analyzeIncidentsFile(file);
}

export function getIncidentsExportUrl(): string {
  return `${getBaseUrl()}/api/incidents/results/export`;
}
