import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RegisterPage from "@/app/register/page";
import ProfilePage from "@/app/account/profile/page";
import { authApi } from "@/lib/auth/api";

const push = vi.fn();
const replace = vi.fn();
const register = vi.fn();
const refreshUser = vi.fn();

const authenticatedUser = {
  id: "1",
  email: "manager@brasaland.com",
  role: "manager",
  is_active: true,
  profile: {
    id: "10",
    user_id: "1",
    name: "Lucía Fernández",
    phone: "+57 300 111 2233",
    address: "Medellín",
  },
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace }),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: authenticatedUser,
    loading: false,
    register,
    refreshUser,
  }),
}));

describe("authentication account pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("registers a user and enters the protected overview", async () => {
    register.mockResolvedValue(undefined);
    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "nuevo@brasaland.com" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "Password1!" },
    });
    fireEvent.change(screen.getByLabelText("Confirmar contraseña"), {
      target: { value: "Password1!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Crear cuenta/i }));

    await waitFor(() => {
      expect(register).toHaveBeenCalledWith({
        email: "nuevo@brasaland.com",
        password: "Password1!",
        name: undefined,
        phone: undefined,
        address: undefined,
      });
      expect(push).toHaveBeenCalledWith("/backoffice/overview");
    });
  });

  it("updates the authenticated user's profile", async () => {
    const updateProfile = vi.spyOn(authApi, "updateProfile").mockResolvedValue({
      ...authenticatedUser.profile,
      name: "Lucía F. Guerrero",
    });
    refreshUser.mockResolvedValue(undefined);
    render(<ProfilePage />);

    fireEvent.click(screen.getByRole("button", { name: "Editar Perfil" }));
    fireEvent.change(screen.getByLabelText("Nombre completo"), {
      target: { value: "Lucía F. Guerrero" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar Cambios" }));

    await waitFor(() => {
      expect(updateProfile).toHaveBeenCalledWith({
        name: "Lucía F. Guerrero",
        phone: "+57 300 111 2233",
        address: "Medellín",
      });
      expect(refreshUser).toHaveBeenCalled();
    });
  });
});
