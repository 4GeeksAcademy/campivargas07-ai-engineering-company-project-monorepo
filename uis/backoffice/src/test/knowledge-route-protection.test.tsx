import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BackofficeKnowledgePage from "@/app/backoffice/knowledge/page";
import { useAuth } from "@/lib/auth";

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/backoffice/knowledge",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
  authApi: { getToken: () => "session-token", logout: vi.fn() },
}));

describe("Knowledge route protection", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.restoreAllMocks());

  function session(loading: boolean, authenticated = false) {
    vi.mocked(useAuth).mockReturnValue({
      user: authenticated ? {
        user: { id: "user-1", email: "user@example.com", role: "user", is_active: true, created_at: "2026-10-14T00:00:00Z" },
        profile: null,
      } : null,
      loading,
      login: vi.fn(), register: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(),
    });
  }

  it("withholds the internal header and form while restoring a session", () => {
    session(true);
    render(<BackofficeKnowledgePage />);
    expect(screen.getByText("Verificando sesión...")).toBeInTheDocument();
    expect(screen.queryByText("Brasaland Backoffice")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("¿Qué necesitas saber?")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects anonymous users without displaying the internal form", () => {
    session(false);
    render(<BackofficeKnowledgePage />);
    expect(replace).toHaveBeenCalledWith("/login");
    expect(screen.queryByText("Brasaland Backoffice")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("¿Qué necesitas saber?")).not.toBeInTheDocument();
  });

  it("displays the protected Knowledge form when the session is confirmed", () => {
    session(false, true);
    render(<BackofficeKnowledgePage />);
    expect(screen.getByLabelText("¿Qué necesitas saber?")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /conocimiento/i })).toHaveAttribute("href", "/backoffice/knowledge");
    expect(replace).not.toHaveBeenCalled();
  });

  it("wires the confirmed session, protected form, Bearer request and visible answer", async () => {
    session(false, true);
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(
      JSON.stringify({ answer: "Respuesta de prueba del manual." }), { status: 200 },
    ));
    render(<BackofficeKnowledgePage />);
    fireEvent.change(screen.getByLabelText("¿Qué necesitas saber?"), { target: { value: "¿Qué aplica?" } });
    fireEvent.click(screen.getByRole("button", { name: "Consultar" }));
    expect(await screen.findByLabelText("Respuesta del asistente")).toHaveTextContent("Respuesta de prueba del manual.");
    expect(fetchMock).toHaveBeenCalledWith("/api/knowledge/query", expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer session-token" }),
      body: JSON.stringify({ question: "¿Qué aplica?" }),
    }));
  });
});
