import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { InboundOrderForm } from "@/components/inventory/inbound-order-form";
import { OutboundOrderForm } from "@/components/inventory/outbound-order-form";
import { inventoryApi, InventoryApiError } from "@/lib/inventory";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("local_id=MED-001&ingredient_id=ing-1"),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/backoffice/inventory/orders/inbound",
}));

vi.mock("@/lib/inventory", () => ({
  inventoryApi: {
    listProducts: vi.fn(),
    getProduct: vi.fn(),
    createInboundOrder: vi.fn(),
    createOutboundOrder: vi.fn(),
  },
  InventoryApiError: class extends Error {
    status: number;
    detail: string;
    constructor(status: number, detail: string) {
      super(detail);
      this.status = status;
      this.detail = detail;
    }
  },
}));

describe("Inventory Orders Forms", () => {
  const mockIngredients = [
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
      current_stock: 15,
    },
    {
      id: "ing-2",
      sku: "ING-002",
      name: "Pollo Entero (kg)",
      category: "carne",
      unit_of_measure: "kg",
      minimum_stock: 10,
      perishable: true,
      created_at: "2026-09-12T00:00:00Z",
      local_id: "MED-001",
      current_stock: 25,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(inventoryApi.listProducts).mockResolvedValue(mockIngredients);
    vi.mocked(inventoryApi.getProduct).mockResolvedValue(mockIngredients[0]);
  });

  describe("InboundOrderForm", () => {
    it("submits inbound order successfully, increments stock balance, and clears quantity", async () => {
      vi.mocked(inventoryApi.createInboundOrder).mockResolvedValue({
        id: "ord-1",
        type: "inbound",
        ingredient_id: "ing-1",
        ingredient_sku: "ING-001",
        ingredient_name: "Carne de Res (kg)",
        local_id: "MED-001",
        quantity: 20,
        user_uuid: "user-123",
        created_at: "2026-09-12T00:00:00Z",
      });
      vi.mocked(inventoryApi.getProduct).mockResolvedValue({
        ...mockIngredients[0],
        current_stock: 35,
      });

      render(<InboundOrderForm />);

      await waitFor(() => {
        expect(screen.getByText(/Carne de Res/i)).toBeInTheDocument();
      });

      // Initial visible stock is 15 kg
      expect(screen.getByText("15 kg")).toBeInTheDocument();

      const qtyInput = screen.getByLabelText(/Cantidad a ingresar/i);
      fireEvent.change(qtyInput, { target: { value: "20" } });

      const submitBtn = screen.getByRole("button", { name: /Registrar Entrada de Stock/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Entrada registrada exitosamente/i)).toBeInTheDocument();
      });

      expect(inventoryApi.createInboundOrder).toHaveBeenCalledWith({
        ingredient_id: "ing-1",
        local_id: "MED-001",
        quantity: 20,
      });

      // Stock balance should immediately reflect the increase: 15 + 20 = 35 kg
      expect(screen.getByText("35 kg")).toBeInTheDocument();

      // Quantity input should be reset
      expect((qtyInput as HTMLInputElement).value).toBe("");
    });

    it("rejects non-positive quantity client-side without calling API", async () => {
      render(<InboundOrderForm />);

      await waitFor(() => {
        expect(screen.getByText(/Carne de Res/i)).toBeInTheDocument();
      });

      const qtyInput = screen.getByLabelText(/Cantidad a ingresar/i);
      fireEvent.change(qtyInput, { target: { value: "0" } });

      const submitBtn = screen.getByRole("button", { name: /Registrar Entrada de Stock/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/La cantidad debe ser un número estrictamente mayor a 0/i)).toBeInTheDocument();
      });

      expect(inventoryApi.createInboundOrder).not.toHaveBeenCalled();
    });

    it("displays error message and retains form values on failure", async () => {
      vi.mocked(inventoryApi.createInboundOrder).mockRejectedValue(
        new InventoryApiError(400, "Error de validación en la orden")
      );

      render(<InboundOrderForm />);

      await waitFor(() => {
        expect(screen.getByText(/Carne de Res/i)).toBeInTheDocument();
      });

      const qtyInput = screen.getByLabelText(/Cantidad a ingresar/i);
      fireEvent.change(qtyInput, { target: { value: "10" } });

      const submitBtn = screen.getByRole("button", { name: /Registrar Entrada de Stock/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Error de validación en la orden/i)).toBeInTheDocument();
      });

      // Quantity must NOT be cleared on error
      expect((qtyInput as HTMLInputElement).value).toBe("10");
    });

    it("handles getProduct failure after successful order: shows order confirmation, reconciliation warning, and retry button", async () => {
      vi.mocked(inventoryApi.createInboundOrder).mockResolvedValue({
        id: "ord-1",
        type: "inbound",
        ingredient_id: "ing-1",
        ingredient_sku: "ING-001",
        ingredient_name: "Carne de Res (kg)",
        local_id: "MED-001",
        quantity: 20,
        user_uuid: "user-123",
        created_at: "2026-09-12T00:00:00Z",
      });
      // Reconciliation call fails
      vi.mocked(inventoryApi.getProduct).mockRejectedValueOnce(
        new Error("Network error during reconciliation")
      );

      render(<InboundOrderForm />);

      await waitFor(() => {
        expect(screen.getByText(/Carne de Res/i)).toBeInTheDocument();
      });

      const qtyInput = screen.getByLabelText(/Cantidad a ingresar/i);
      fireEvent.change(qtyInput, { target: { value: "20" } });

      const submitBtn = screen.getByRole("button", { name: /Registrar Entrada de Stock/i });
      fireEvent.click(submitBtn);

      // Order confirmation is visible
      await waitFor(() => {
        expect(screen.getByText(/Entrada registrada exitosamente/i)).toBeInTheDocument();
      });

      // Optimistic balance is updated (15 + 20 = 35)
      expect(screen.getByText("35 kg")).toBeInTheDocument();

      // Reconciliation warning is visible
      expect(
        screen.getByText(/no pudo recuperarse el balance actualizado desde el servidor/i)
      ).toBeInTheDocument();

      // Retry button is available
      const retryBtn = screen.getByRole("button", { name: /Reintentar sincronización/i });
      expect(retryBtn).toBeInTheDocument();

      // Clicking retry succeeds
      vi.mocked(inventoryApi.getProduct).mockResolvedValueOnce({
        ...mockIngredients[0],
        current_stock: 35,
      });
      fireEvent.click(retryBtn);

      await waitFor(() => {
        expect(
          screen.queryByText(/no pudo recuperarse el balance actualizado desde el servidor/i)
        ).not.toBeInTheDocument();
      });
    });
  });

  describe("OutboundOrderForm", () => {
    it("shows reactive stock balance, warns and disables submit when requested quantity exceeds stock", async () => {
      render(<OutboundOrderForm />);

      await waitFor(() => {
        expect(screen.getByText(/Stock disponible actual en/i)).toBeInTheDocument();
        expect(screen.getByText("15 kg")).toBeInTheDocument();
      });

      const qtyInput = screen.getByLabelText(/Cantidad a retirar/i);
      const submitBtn = screen.getByRole("button", { name: /Registrar Salida de Stock/i });

      // Type quantity exceeding available stock (20 > 15)
      fireEvent.change(qtyInput, { target: { value: "20" } });

      await waitFor(() => {
        expect(screen.getByText(/Advertencia de sobregiro/i)).toBeInTheDocument();
      });

      // Preemptive submit button disable
      expect(submitBtn).toBeDisabled();
    });

    it("handles HTTP 400 InsufficientStockError cleanly inline next to quantity field", async () => {
      const errorMsg = "Insufficient stock for ingredient 'Carne de Res (kg)' (SKU: ING-001) in restaurant 'MED-001'. Available: 15, requested: 12";
      vi.mocked(inventoryApi.createOutboundOrder).mockRejectedValue(
        new InventoryApiError(400, errorMsg)
      );

      render(<OutboundOrderForm />);

      await waitFor(() => {
        expect(screen.getByText("15 kg")).toBeInTheDocument();
      });

      const qtyInput = screen.getByLabelText(/Cantidad a retirar/i);
      // Valid quantity client-side but rejected by backend
      fireEvent.change(qtyInput, { target: { value: "12" } });

      const submitBtn = screen.getByRole("button", { name: /Registrar Salida de Stock/i });
      expect(submitBtn).not.toBeDisabled();
      fireEvent.click(submitBtn);

      await waitFor(() => {
        const alert = screen.getByRole("alert");
        expect(alert).toHaveTextContent(errorMsg);
      });

      // Form value is preserved so user can adjust
      expect((qtyInput as HTMLInputElement).value).toBe("12");
    });

    it("records outbound order successfully, decrements stock balance, and resets quantity", async () => {
      vi.mocked(inventoryApi.createOutboundOrder).mockResolvedValue({
        id: "ord-out-1",
        type: "outbound",
        ingredient_id: "ing-1",
        ingredient_sku: "ING-001",
        ingredient_name: "Carne de Res (kg)",
        local_id: "MED-001",
        quantity: 5,
        user_uuid: "user-123",
        created_at: "2026-09-12T00:00:00Z",
      });
      vi.mocked(inventoryApi.getProduct).mockImplementation(async () => {
        if (vi.mocked(inventoryApi.createOutboundOrder).mock.calls.length > 0) {
          return { ...mockIngredients[0], current_stock: 10 };
        }
        return mockIngredients[0];
      });

      render(<OutboundOrderForm />);

      await waitFor(() => {
        expect(screen.getByText("15 kg")).toBeInTheDocument();
      });

      const qtyInput = screen.getByLabelText(/Cantidad a retirar/i);
      fireEvent.change(qtyInput, { target: { value: "5" } });

      const submitBtn = screen.getByRole("button", { name: /Registrar Salida de Stock/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText(/Salida registrada exitosamente/i)).toBeInTheDocument();
      });

      expect(inventoryApi.createOutboundOrder).toHaveBeenCalledWith({
        ingredient_id: "ing-1",
        local_id: "MED-001",
        quantity: 5,
      });

      // Stock balance should immediately reflect the decrease: 15 - 5 = 10 kg
      await waitFor(() => {
        expect(screen.getByText("10 kg")).toBeInTheDocument();
      });
      expect((qtyInput as HTMLInputElement).value).toBe("");
    });
  });
});
