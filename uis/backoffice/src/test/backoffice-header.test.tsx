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
    expect(incidentsLink).not.toHaveClass("nav-link-active");
  });

  it("marks incidents link as active when activeView is 'incidents'", () => {
    render(<BackofficeHeader activeView="incidents" badge="Hito 4" />);

    const overviewLink = screen.getByRole("link", { name: "Resumen" });
    const incidentsLink = screen.getByRole("link", { name: "Incidencias" });

    expect(incidentsLink).toHaveClass("nav-link-active");
    expect(overviewLink).not.toHaveClass("nav-link-active");
  });
});

