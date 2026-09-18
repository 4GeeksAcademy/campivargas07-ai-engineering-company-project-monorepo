import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthGuard } from "@/components/auth-guard";
import { useAuth } from "@/lib/auth";

const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockReplace,
  }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

describe("Route Protection & AuthGuard", () => {
  beforeEach(() => {
    localStorage.clear();
    mockReplace.mockClear();
    vi.clearAllMocks();
  });

  it("shows loading indicator when auth state is loading", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <AuthGuard>
        <div>Contenido Protegido</div>
      </AuthGuard>
    );

    expect(screen.getByText(/Verificando sesión/i)).toBeInTheDocument();
    expect(screen.queryByText("Contenido Protegido")).not.toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("redirects unauthenticated user to /login without flashing protected content", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <AuthGuard>
        <div>Contenido Protegido</div>
      </AuthGuard>
    );

    expect(mockReplace).toHaveBeenCalledWith("/login");
    // Protected content MUST NOT be displayed
    expect(screen.queryByText("Contenido Protegido")).not.toBeInTheDocument();
    expect(screen.getByText(/Redirigiendo a inicio de sesión/i)).toBeInTheDocument();
  });

  it("renders children without redirect when authenticated user exists", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        user: {
          id: "user-1",
          email: "felipe@brasaland.co",
          role: "admin",
          is_active: true,
          created_at: "2026-09-18T00:00:00Z",
        },
        profile: null,
      },
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(
      <AuthGuard>
        <div>Contenido Protegido</div>
      </AuthGuard>
    );

    expect(screen.getByText("Contenido Protegido")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
