import { authApi } from "@/lib/auth";

export type KnowledgeQueryResponse = { answer: string };

export async function askKnowledge(question: string): Promise<KnowledgeQueryResponse> {
  const token = authApi.getToken();
  if (!token) {
    throw new Error("No hay una sesión activa. Inicia sesión nuevamente.");
  }
  const response = await fetch("/api/knowledge/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question }),
  });
  if (response.status === 401) {
    authApi.logout();
    throw new Error("La sesión expiró. Inicia sesión nuevamente.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(payload?.detail || `No se pudo consultar la base (${response.status}).`);
  }
  const payload = await response.json() as Partial<KnowledgeQueryResponse>;
  if (typeof payload.answer !== "string" || !payload.answer.trim()) {
    throw new Error("La respuesta recibida no tiene el formato esperado.");
  }
  return { answer: payload.answer };
}
