import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { OrdersLedger } from "@/components/inventory/orders-ledger";
import { inventoryApi } from "@/lib/inventory";

vi.mock("@/lib/inventory", () => ({
  inventoryApi: {
    listOrders: vi.fn(),
  },
}));

describe("OrdersLedger Component", () => {
  const mockOrdersResponse = {
    orders: [
      {
        id: "ord-1",
        type: "inbound" as const,
        ingredient_id: "ing-1",
        ingredient_sku: "ING-001",
        ingredient_name: "Carne de Res (kg)",
        local_id: "MED-001",
        quantity: 50,
        user_uuid: "11111111-1111-1111-1111-111111111111",
        created_at: "2026-09-12T10:30:00Z",
      },
      {
        id: "ord-2",
        type: "outbound" as const,
        ingredient_id: "ing-1",
        ingredient_sku: "ING-001",
        ingredient_name: "Carne de Res (kg)",
        local_id: "MED-001",
        quantity: 12,
        user_uuid: "22222222-2222-2222-2222-222222222222",
        created_at: "2026-09-12T11:00:00Z",
      },
    ],
    total: 2,
  };

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("loads and displays orders with visual textual badges, localized date and user uuid", async () => {
    vi.mocked(inventoryApi.listOrders).mockResolvedValue(mockOrdersResponse);

    render(<OrdersLedger />);

    expect(screen.getByText(/Cargando historial de órdenes/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("ENTRADA")).toBeInTheDocument();
      expect(screen.getByText("SALIDA")).toBeInTheDocument();
      expect(screen.getByText("+50")).toBeInTheDocument();
      expect(screen.getByText("-12")).toBeInTheDocument();
    });

    // Check SKU, Name, user UUID
    const skus = screen.getAllByText("ING-001");
    expect(skus.length).toBe(2);

    expect(screen.getByText("11111111-1111-1111-1111-111111111111")).toBeInTheDocument();
    expect(screen.getByText("22222222-2222-2222-2222-222222222222")).toBeInTheDocument();

    // Check sede label
    expect(screen.getAllByText(/Brasaland El Poblado \(MED-001\)/i).length).toBeGreaterThan(0);
  });

  it("filters orders by type", async () => {
    vi.mocked(inventoryApi.listOrders).mockResolvedValue(mockOrdersResponse);

    render(<OrdersLedger />);

    await waitFor(() => {
      expect(screen.getByText("ENTRADA")).toBeInTheDocument();
    });

    const typeSelect = screen.getByLabelText(/Tipo:/i);
    fireEvent.change(typeSelect, { target: { value: "inbound" } });

    await waitFor(() => {
      expect(inventoryApi.listOrders).toHaveBeenCalledWith(
        expect.objectContaining({ type: "inbound" })
      );
    });
  });

  it("filters orders by restaurant", async () => {
    vi.mocked(inventoryApi.listOrders).mockResolvedValue(mockOrdersResponse);

    render(<OrdersLedger />);

    await waitFor(() => {
      expect(screen.getByText("ENTRADA")).toBeInTheDocument();
    });

    const localSelect = screen.getByLabelText(/Sede:/i);
    fireEvent.change(localSelect, { target: { value: "MIA-001" } });

    await waitFor(() => {
      expect(inventoryApi.listOrders).toHaveBeenCalledWith(
        expect.objectContaining({ local_id: "MIA-001" })
      );
    });
  });

  it("renders empty state with action CTAs when no orders exist", async () => {
    vi.mocked(inventoryApi.listOrders).mockResolvedValue({ orders: [], total: 0 });

    render(<OrdersLedger />);

    await waitFor(() => {
      expect(screen.getByText(/No se encontraron órdenes para la sede o filtro seleccionado/i)).toBeInTheDocument();
    });

    expect(screen.getByRole("link", { name: /\+ Registrar entrada/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /- Registrar salida/i })).toBeInTheDocument();
  });
});
