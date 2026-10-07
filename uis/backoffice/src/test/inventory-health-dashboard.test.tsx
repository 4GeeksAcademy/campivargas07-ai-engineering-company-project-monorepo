import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import {
  InventoryHealthDashboard,
  type InventoryHealthResponse,
} from "@/components/reporting/inventory-health-dashboard";

const mockSuccessData: InventoryHealthResponse = {
  period: {
    snapshot_date: "2026-09-28",
    data_freshness_timestamp: "2026-09-28T14:30:00Z",
    freshness_lag_seconds: 300, // 5 min lag, healthy
  },
  summary: {
    total_locations_reported: 2,
    total_ingredients_monitored: 3,
    critical_stockouts_count: 1,
    below_minimum_count: 1,
    average_stock_level_ratio: 0.95,
    insufficient_stock_attempts_count: 2,
  },
  items: [
    {
      local_id: "MED-001",
      ingredient_id: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      ingredient_sku: "ING-001",
      ingredient_name: "Carne de Res Brasa",
      category: "carne",
      unit_of_measure: "kg",
      current_stock: 0.0,
      minimum_stock: 25.0,
      stock_level_ratio: 0.0,
      stock_deficit: 25.0,
      is_stockout: true,
      is_below_minimum: false,
      inbound_quantity: 0.0,
      outbound_quantity: 25.0,
      insufficient_stock_attempts_count: 2,
      source_event_count: 3,
      computed_at: "2026-09-28T14:30:00Z",
    },
    {
      local_id: "MED-001",
      ingredient_id: "4a2ceb3c-2a6c-4cad-8acc-1a0c6a2cba5c",
      ingredient_sku: "ING-002",
      ingredient_name: "Pechuga de Pollo",
      category: "carne",
      unit_of_measure: "kg",
      current_stock: 15.0,
      minimum_stock: 20.0,
      stock_level_ratio: 0.75,
      stock_deficit: 5.0,
      is_stockout: false,
      is_below_minimum: true,
      inbound_quantity: 20.0,
      outbound_quantity: 5.0,
      insufficient_stock_attempts_count: 0,
      source_event_count: 2,
      computed_at: "2026-09-28T14:30:00Z",
    },
    {
      local_id: "MIA-001",
      ingredient_id: "5b3dfb4d-3b7d-4bad-9bdd-3b0d7b3dcb7e",
      ingredient_sku: "ING-003",
      ingredient_name: "Papas Rústicas",
      category: "verdura",
      unit_of_measure: "kg",
      current_stock: 60.0,
      minimum_stock: 30.0,
      stock_level_ratio: 2.0,
      stock_deficit: 0.0,
      is_stockout: false,
      is_below_minimum: false,
      inbound_quantity: 40.0,
      outbound_quantity: 10.0,
      insufficient_stock_attempts_count: 0,
      source_event_count: 4,
      computed_at: "2026-09-28T14:30:00Z",
    },
  ],
  pipeline_run_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
};

const mockEmptyData: InventoryHealthResponse = {
  period: {
    snapshot_date: "2026-09-28",
    data_freshness_timestamp: null,
    freshness_lag_seconds: null,
  },
  summary: {
    total_locations_reported: 0,
    total_ingredients_monitored: 0,
    critical_stockouts_count: 0,
    below_minimum_count: 0,
    average_stock_level_ratio: 0.0,
    insufficient_stock_attempts_count: 0,
  },
  items: [],
  pipeline_run_id: null,
};

describe("InventoryHealthDashboard Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows loading state initially while fetching inventory health", () => {
    const pendingPromise = new Promise(() => {});
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pendingPromise));

    render(<InventoryHealthDashboard />);

    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.getByText(/Cargando indicadores de salud de inventario/i)).toBeInTheDocument();
  });

  it("renders 4 KPIs, metadata, and detail table successfully upon resolution", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockSuccessData,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryHealthDashboard />);

    await waitFor(() => {
      expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    });

    // Header and title
    expect(screen.getByText("Salud de Inventario — Desempeño de Negocio")).toBeInTheDocument();
    expect(screen.getByText("2026-09-28")).toBeInTheDocument();

    // 4 KPI Cards
    const ratioCard = screen.getByTestId("kpi-stock-ratio");
    expect(within(ratioCard).getByText("METRIC_STOCK_LEVEL_RATIO")).toBeInTheDocument();
    expect(within(ratioCard).getByText("0.95x")).toBeInTheDocument();

    const stockoutsCard = screen.getByTestId("kpi-critical-stockouts");
    expect(within(stockoutsCard).getByText("METRIC_CRITICAL_STOCKOUTS_COUNT")).toBeInTheDocument();
    expect(within(stockoutsCard).getByText("1")).toBeInTheDocument();

    const belowMinCard = screen.getByTestId("kpi-below-minimum");
    expect(within(belowMinCard).getByText("METRIC_BELOW_MINIMUM_COUNT")).toBeInTheDocument();
    expect(within(belowMinCard).getByText("1")).toBeInTheDocument();

    const attemptsCard = screen.getByTestId("kpi-insufficient-attempts");
    expect(within(attemptsCard).getByText("METRIC_INSUFFICIENT_STOCK_ATTEMPTS_COUNT")).toBeInTheDocument();
    expect(within(attemptsCard).getByText("2")).toBeInTheDocument();

    // Table rows
    expect(screen.getByText("Carne de Res Brasa")).toBeInTheDocument();
    expect(screen.getByText("ING-001")).toBeInTheDocument();
    expect(screen.getByText("Agotado")).toBeInTheDocument();

    expect(screen.getByText("Pechuga de Pollo")).toBeInTheDocument();
    expect(screen.getByText("Bajo Mínimo")).toBeInTheDocument();

    expect(screen.getByText("Papas Rústicas")).toBeInTheDocument();
    expect(screen.getByText("Saludable")).toBeInTheDocument();

    // Insufficient stock blocked attempt badge
    expect(screen.getByText("2 bloqueos")).toBeInTheDocument();
  });

  it("renders empty state when response has no items", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockEmptyData,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryHealthDashboard />);

    await waitFor(() => {
      expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    });

    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.getByText("Sin datos de inventario disponibles")).toBeInTheDocument();
  });

  it("renders error state when query fails and allows retrying", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("Conexión rechazada al endpoint"));
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryHealthDashboard />);

    await waitFor(() => {
      expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    });

    expect(screen.getByTestId("error-state")).toBeInTheDocument();
    expect(screen.getByText(/Error al consultar indicadores de inventario/i)).toBeInTheDocument();

    // Now mock success for retry
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSuccessData,
    });

    const retryButton = screen.getByRole("button", { name: /Reintentar/i });
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
      expect(screen.getByText("Carne de Res Brasa")).toBeInTheDocument();
    });
  });

  it("displays stale warning indicator when freshness lag exceeds 20 minutes", async () => {
    const staleData: InventoryHealthResponse = {
      ...mockSuccessData,
      period: {
        snapshot_date: "2026-09-28",
        data_freshness_timestamp: "2026-09-28T12:00:00Z",
        freshness_lag_seconds: 1800, // 30 minutes lag (> 20 min)
      },
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => staleData,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<InventoryHealthDashboard />);

    await waitFor(() => {
      expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    });

    expect(screen.getByTestId("stale-warning")).toBeInTheDocument();
    expect(screen.getByText(/Información Desactualizada \(Retraso de Sincronización\)/i)).toBeInTheDocument();
    expect(screen.getByText(/superando la tolerancia máxima de 20 minutos/i)).toBeInTheDocument();
  });
});
