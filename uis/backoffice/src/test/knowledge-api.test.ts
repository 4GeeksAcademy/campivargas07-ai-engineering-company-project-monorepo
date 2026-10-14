import { afterEach, describe, expect, it, vi } from "vitest";
import { askKnowledge } from "@/lib/knowledge-api";
import { authApi } from "@/lib/auth/api";

vi.mock("@/lib/auth/api", () => ({ authApi: { getToken: vi.fn(), logout: vi.fn() } }));

describe("askKnowledge", () => {
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
    await expect(askKnowledge("pregunta")).rejects.toThrow(/sesión/i);
  });

  it("logs out on expired sessions", async () => {
    vi.mocked(authApi.getToken).mockReturnValue("expired");
    vi.spyOn(global, "fetch").mockResolvedValue(new Response("{}", { status: 401 }));
    await expect(askKnowledge("pregunta")).rejects.toThrow();
    expect(authApi.logout).toHaveBeenCalledOnce();
  });
});
