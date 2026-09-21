import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ProductsTable } from "@/components/inventory/products-table";
import { inventoryApi } from "@/lib/inventory";

vi.mock("@/lib/inventory", () => ({
  inventoryApi: {
    listProducts: vi.fn(),
  },
}));

describe("ProductsTable Component", () => {
  const mockProducts = [
    {
      id: "ing-1",
      sku: "ING-001",
      name: "Carne de Res (kg)",
      category: "carne",
      unit_of_measure: "kg",
      minimum_stock: 20,
      perishable: true,
      created_at: "2026-09-12T00:00:00Z",
      local_id: "MED-001",
      current_stock: 8, // Bajo stock (8 <= 20)
    },
    {
      id: "ing-2",
      sku: "ING-002",
      name: "Pollo Entero (kg)",
      category: "carne",
      unit_of_measure: "kg",
      minimum_stock: 15,
      perishable: true,
      created_at: "2026-09-12T00:00:00Z",
      local_id: "MED-001",
      current_stock: 25, // Saludable (25 > 15)
    },
    {
      id: "ing-3",
      sku: "ING-003",
      name: "Tomate (kg)",
      category: "verdura",
      unit_of_measure: "kg",
      minimum_stock: 10,
      perishable: true,
      created_at: "2026-09-12T00:00:00Z",
      local_id: "MED-001",
      current_stock: 0, // Agotado (0 <= 0)
    },
  ];

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("loads and displays products with correct stock badges", async () => {
    vi.mocked(inventoryApi.listProducts).mockResolvedValue(mockProducts);

    render(<ProductsTable />);

    expect(screen.getByText(/Cargando inventario/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Carne de Res (kg)")).toBeInTheDocument();
      expect(screen.getByText("Pollo Entero (kg)")).toBeInTheDocument();
      expect(screen.getByText("Tomate (kg)")).toBeInTheDocument();
    });

    // Check explicit textual semaphore badges
    expect(screen.getByText(/Stock bajo/i)).toBeInTheDocument();
    expect(screen.getByText("Saludable")).toBeInTheDocument();
    expect(screen.getByText("Agotado")).toBeInTheDocument();

    // Check action buttons exist
    const entradaLinks = screen.getAllByRole("link", { name: /\+ Entrada/i });
    expect(entradaLinks.length).toBe(3);
    expect(entradaLinks[0]).toHaveAttribute(
      "href",
      "/backoffice/inventory/orders/inbound?local_id=MED-001&ingredient_id=ing-1"
    );

    const salidaLinks = screen.getAllByRole("link", { name: /- Salida/i });
    expect(salidaLinks.length).toBe(3);
    expect(salidaLinks[0]).toHaveAttribute(
      "href",
      "/backoffice/inventory/orders/outbound?local_id=MED-001&ingredient_id=ing-1"
    );
  });

  it("changes restaurant and reloads data", async () => {
    vi.mocked(inventoryApi.listProducts).mockResolvedValue(mockProducts);

    render(<ProductsTable />);

    await waitFor(() => {
      expect(screen.getByText("Carne de Res (kg)")).toBeInTheDocument();
    });

    expect(inventoryApi.listProducts).toHaveBeenCalledWith("MED-001");

    const select = screen.getByLabelText(/Restaurante:/i);
    fireEvent.change(select, { target: { value: "MIA-001" } });

    await waitFor(() => {
      expect(inventoryApi.listProducts).toHaveBeenCalledWith("MIA-001");
    });
  });

  it("renders empty state with CTA when no products are found", async () => {
    vi.mocked(inventoryApi.listProducts).mockResolvedValue([]);

    render(<ProductsTable />);

    await waitFor(() => {
      expect(screen.getByText(/No se encontraron ingredientes registrados/i)).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: /\+ Registrar primera entrada/i })).toBeInTheDocument();
  });
});
