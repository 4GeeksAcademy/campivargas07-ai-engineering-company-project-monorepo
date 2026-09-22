import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import {
  TelemetryReportDashboard,
  type TelemetryReportData,
} from "@/components/telemetry/telemetry-report-dashboard";

const mockSuccessData: TelemetryReportData = {
  period: {
    from: "2026-09-15T00:00:00Z",
    to: "2026-09-22T00:00:00Z",
  },
  metrics: {
    events_per_day: [
      { date: "2026-09-20", event_count: 14 },
      { date: "2026-09-21", event_count: 22 },
    ],
    error_rate_by_type: [
      { event_type: "form_validation_failed", error_count: 4, error_rate: 66.67 },
      { event_type: "system_exception_captured", error_count: 2, error_rate: 33.33 },
    ],
    login_failure_rate_per_day: [
      {
        date: "2026-09-20",
        successful_logins: 9,
        failed_logins: 1,
        total_attempts: 10,
        login_failure_rate: 10.0,
      },
    ],
    api_latency_by_route: [
      {
        route_path: "/inventory/orders",
        request_count: 20,
        average_duration_ms: 180.5,
        p95_duration_ms: 320.0,
      },
      {
        route_path: "/inventory/products",
        request_count: 50,
        average_duration_ms: 45.2,
        p95_duration_ms: 88.0,
      },
    ],
  },
};

const mockEmptyData: TelemetryReportData = {
  period: {
    from: "2026-09-15T00:00:00Z",
    to: "2026-09-22T00:00:00Z",
  },
  metrics: {
    events_per_day: [],
    error_rate_by_type: [],
    login_failure_rate_per_day: [],
    api_latency_by_route: [],
  },
};

describe("TelemetryReportDashboard Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows loading state initially while fetching report", () => {
    // Unresolved promise simulates in-flight request
    const pendingPromise = new Promise(() => {});
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(pendingPromise));

    render(<TelemetryReportDashboard />);

    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
    expect(screen.getByText(/Cargando reporte de telemetría/i)).toBeInTheDocument();
  });

  it("renders report metrics and period successfully upon resolution", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockSuccessData,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<TelemetryReportDashboard />);

    // Wait for loading to disappear
    await waitFor(() => {
      expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    });

    // Check title and period
    expect(screen.getByText("Reporte Técnico de Telemetría")).toBeInTheDocument();
    expect(screen.getByTestId("report-period")).toBeInTheDocument();

    // Check metric 1 (events_per_day)
    expect(screen.getByText("Volumen Diario de Eventos")).toBeInTheDocument();
    expect(screen.getAllByText("2026-09-20").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("14 eventos")).toBeInTheDocument();
    expect(screen.getByText("22 eventos")).toBeInTheDocument();

    // Check metric 2 (error_rate_by_type)
    expect(screen.getByText("Errores Técnicos por Tipo")).toBeInTheDocument();
    expect(screen.getByText("form_validation_failed")).toBeInTheDocument();
    expect(screen.getByText("66.7%")).toBeInTheDocument();

    // Check metric 3 (login_failure_rate_per_day)
    expect(screen.getByText("Fallos de Autenticación Diarios")).toBeInTheDocument();
    expect(screen.getByText("10.0%")).toBeInTheDocument();

    // Check metric 4 (api_latency_by_route)
    expect(screen.getByText("Latencia de API por Ruta")).toBeInTheDocument();
    expect(screen.getByText("/inventory/orders")).toBeInTheDocument();
    expect(screen.getByText("/inventory/products")).toBeInTheDocument();
    expect(screen.getByText("320.0 ms")).toBeInTheDocument();
    expect(screen.getByText("88.0 ms")).toBeInTheDocument();
  });

  it("renders empty state when there are no events in the period", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockEmptyData,
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<TelemetryReportDashboard />);

    await waitFor(() => {
      expect(screen.queryByTestId("loading-state")).not.toBeInTheDocument();
    });

    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.getByText("Sin datos de telemetría")).toBeInTheDocument();
    expect(screen.getByText(/No se registraron eventos en el periodo/i)).toBeInTheDocument();
  });

  it("renders error state when fetch fails and allows retrying", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 503,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSuccessData,
      });

    vi.stubGlobal("fetch", fetchMock);

    render(<TelemetryReportDashboard />);

    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
    });

    expect(screen.getByText("Error al cargar telemetría")).toBeInTheDocument();
    expect(
      screen.getByText(/El servicio de base de datos no está disponible temporalmente/i),
    ).toBeInTheDocument();

    // Click retry button
    const retryBtn = screen.getByRole("button", { name: "Reintentar" });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("error-state")).not.toBeInTheDocument();
    });

    expect(screen.getByText("Reporte Técnico de Telemetría")).toBeInTheDocument();
    expect(screen.getByText("/inventory/orders")).toBeInTheDocument();
  });
});
