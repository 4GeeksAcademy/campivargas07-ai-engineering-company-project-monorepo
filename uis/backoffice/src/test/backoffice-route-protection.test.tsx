import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import RootPage from "@/app/page";
import LegacyIncidentsPage from "@/app/incidents/page";
import LoginPage from "@/app/login/page";
import OverviewPage from "@/app/backoffice/overview/page";
import BackofficeIncidentsPage from "@/app/backoffice/incidents/page";
import InventoryProductsPage from "@/app/backoffice/inventory/products/page";
import { useAuth } from "@/lib/auth";
import { redirect } from "next/navigation";

const mockReplace = vi.fn();
const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
  usePathname: () => "/backoffice/inventory/products",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

describe("Backoffice route protection", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockPush.mockClear();
    vi.clearAllMocks();
  });

  it("starts at login instead of rendering operational data on the public root", () => {
    RootPage();

    expect(redirect).toHaveBeenCalledWith("/login");
  });

  it("keeps the legacy incidents route as a redirect without rendering the analyzer", () => {
    LegacyIncidentsPage();

    expect(redirect).toHaveBeenCalledWith("/backoffice/incidents");
  });

  it("does not show overview metrics or internal navigation to anonymous users", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<OverviewPage />);

    expect(mockReplace).toHaveBeenCalledWith("/login");
    expect(screen.getByText(/Redirigiendo a inicio de sesión/i)).toBeInTheDocument();
    expect(screen.queryByText("Brasaland Backoffice")).not.toBeInTheDocument();
    expect(screen.queryByText("Ventas del periodo")).not.toBeInTheDocument();
    expect(screen.queryByText("Alertas de stock critico")).not.toBeInTheDocument();
  });

  it("does not show the incidents analyzer to anonymous users", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<BackofficeIncidentsPage />);

    expect(mockReplace).toHaveBeenCalledWith("/login");
    expect(screen.queryByText("Brasaland Backoffice")).not.toBeInTheDocument();
    expect(screen.queryByText(/Sube el CSV de incidencias/i)).not.toBeInTheDocument();
  });

  it("does not show the inventory header to anonymous users", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<InventoryProductsPage />);

    expect(mockReplace).toHaveBeenCalledWith("/login");
    expect(screen.queryByText("Brasaland Backoffice")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Inventario" })).not.toBeInTheDocument();
  });

  it("sends authenticated users away from login to the protected overview", async () => {
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

    render(<LoginPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/backoffice/overview");
    });
  });

  it("sends users to the protected overview after a successful login", async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      login,
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "felipe@brasaland.co" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "Password123!" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar a la consola" }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith("felipe@brasaland.co", "Password123!");
      expect(mockPush).toHaveBeenCalledWith("/backoffice/overview");
    });
  });
});
