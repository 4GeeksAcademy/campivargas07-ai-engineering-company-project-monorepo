import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { askKnowledge } from "@/lib/knowledge-api";
import { authApi } from "@/lib/auth/api";

vi.mock("@/lib/auth/api", () => ({ authApi: { getToken: vi.fn(), logout: vi.fn() } }));

describe("askKnowledge", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("sends the question using the authenticated session", async () => {
    vi.mocked(authApi.getToken).mockReturnValue("session-token");
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ answer: "Consulta los manuales." }), { status: 200 }),
    );
    await expect(askKnowledge("¿Qué dice el manual?")).resolves.toEqual({ answer: "Consulta los manuales." });
    expect(fetchMock).toHaveBeenCalledWith("/api/knowledge/query", expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer session-token" }),
      body: JSON.stringify({ question: "¿Qué dice el manual?" }),
    }));
  });

  it("rejects missing sessions", async () => {
    vi.mocked(authApi.getToken).mockReturnValue(null);
    const fetchMock = vi.spyOn(global, "fetch");
    await expect(askKnowledge("pregunta")).rejects.toThrow(/sesión/i);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("logs out on expired sessions", async () => {
    vi.mocked(authApi.getToken).mockReturnValue("expired");
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("{}", { status: 401 }));
    await expect(askKnowledge("pregunta")).rejects.toThrow();
    expect(authApi.logout).toHaveBeenCalledOnce();
  });

  it.each(["null", "[]", "{}", '{"answer":42}', '{"answer":"  "}', "not-json"])(
    "rejects a malformed successful response (%s)", async (body) => {
      vi.mocked(authApi.getToken).mockReturnValue("session-token");
      vi.spyOn(global, "fetch").mockResolvedValue(new Response(body, { status: 200 }));
      await expect(askKnowledge("pregunta")).rejects.toThrow("La respuesta recibida no tiene el formato esperado.");
    },
  );

  it.each(["null", "not-json", '{"detail":[{"msg":"Invalid"}]}'])(
    "handles an unavailable API with a malformed detail (%s)", async (body) => {
      vi.mocked(authApi.getToken).mockReturnValue("session-token");
      vi.spyOn(global, "fetch").mockResolvedValue(new Response(body, { status: 503 }));
      await expect(askKnowledge("pregunta")).rejects.toThrow("No se pudo consultar la base (503).");
      expect(authApi.logout).not.toHaveBeenCalled();
    },
  );

  it("shows the API's public provider failure without returning an answer", async () => {
    vi.mocked(authApi.getToken).mockReturnValue("session-token");
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(
      JSON.stringify({ detail: "El proveedor de conocimiento no está disponible." }),
      { status: 502 },
    ));
    await expect(askKnowledge("pregunta")).rejects.toThrow("El proveedor de conocimiento no está disponible.");
  });

  it("exposes only the public answer from successful payloads", async () => {
    vi.mocked(authApi.getToken).mockReturnValue("session-token");
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      answer: "Respuesta pública.", chunks: [{ text: "internal" }], metadata: { score: 0.8 },
    }), { status: 200 }));
    await expect(askKnowledge("pregunta")).resolves.toEqual({ answer: "Respuesta pública." });
  });
});
