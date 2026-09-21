import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BackofficeHeader } from "@/components/backoffice-header";

describe("BackofficeHeader Component", () => {
  it("renders brand title, description and badge correctly", () => {
    render(<BackofficeHeader activeView="overview" badge="Online" />);

    expect(screen.getByText("Brasaland Backoffice")).toBeInTheDocument();
    expect(screen.getByText(/Operaciones, compras e incidencias/i)).toBeInTheDocument();
    expect(screen.getByText("Online")).toBeInTheDocument();
  });

  it("marks overview link as active when activeView is 'overview'", () => {
    render(<BackofficeHeader activeView="overview" badge="Hito 4" />);

    const overviewLink = screen.getByRole("link", { name: "Resumen" });
    const incidentsLink = screen.getByRole("link", { name: "Incidencias" });

    expect(overviewLink).toHaveClass("nav-link-active");
    expect(overviewLink).toHaveAttribute("href", "/backoffice/overview");
    expect(incidentsLink).not.toHaveClass("nav-link-active");
  });

  it("marks incidents link as active when activeView is 'incidents'", () => {
    render(<BackofficeHeader activeView="incidents" badge="Hito 4" />);

    const overviewLink = screen.getByRole("link", { name: "Resumen" });
    const incidentsLink = screen.getByRole("link", { name: "Incidencias" });

    expect(incidentsLink).toHaveClass("nav-link-active");
    expect(incidentsLink).toHaveAttribute("href", "/backoffice/incidents");
    expect(overviewLink).not.toHaveClass("nav-link-active");
  });

  it("marks inventory link as active when activeView is 'inventory'", () => {
    render(<BackofficeHeader activeView="inventory" badge="Hito 5" />);

    const overviewLink = screen.getByRole("link", { name: "Resumen" });
    const inventoryLink = screen.getByRole("link", { name: "Inventario" });
    const incidentsLink = screen.getByRole("link", { name: "Incidencias" });

    expect(inventoryLink).toHaveClass("nav-link-active");
    expect(inventoryLink).toHaveAttribute("href", "/backoffice/inventory/products");
    expect(overviewLink).not.toHaveClass("nav-link-active");
    expect(incidentsLink).not.toHaveClass("nav-link-active");
  });

  it("links to the protected supplier directory", () => {
    render(<BackofficeHeader activeView="suppliers" badge="Compras" />);

    const suppliersLink = screen.getByRole("link", { name: "Proveedores" });
    expect(suppliersLink).toHaveClass("nav-link-active");
    expect(suppliersLink).toHaveAttribute("href", "/backoffice/suppliers");
  });

  it("links to the authenticated account profile", () => {
    render(<BackofficeHeader activeView="profile" badge="Cuenta" />);

    const profileLink = screen.getByRole("link", { name: "Cuenta" });
    expect(profileLink).toHaveClass("nav-link-active");
    expect(profileLink).toHaveAttribute("href", "/account/profile");
  });
});
