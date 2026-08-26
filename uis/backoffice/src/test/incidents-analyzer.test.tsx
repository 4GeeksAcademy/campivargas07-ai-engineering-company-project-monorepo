import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { IncidentsAnalyzer } from "@/components/incidents-analyzer";
import * as incidentsApi from "@/lib/incidents-api";

describe("IncidentsAnalyzer Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders upload zone and empty state by default", () => {
    render(<IncidentsAnalyzer />);

    expect(screen.getByText("Sube el CSV de incidencias y obtén el resumen validado al instante")).toBeInTheDocument();
    expect(screen.getByText("No hay resultados cargados todavia")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Analizar incidencias/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Descargar CSV/i })).toBeDisabled();
  });

  it("shows error message if analyze is clicked without selecting a file", async () => {
    render(<IncidentsAnalyzer />);

    const analyzeBtn = screen.getByRole("button", { name: /Analizar incidencias/i });
    fireEvent.click(analyzeBtn);

    await waitFor(() => {
      expect(screen.getByText("Selecciona un archivo CSV antes de analizar.")).toBeInTheDocument();
    });
  });

  it("renders analysis KPI cards and breakdown tables after successful analysis", async () => {
    const mockPayload: incidentsApi.IncidentAnalysisResponse = {
      source_file: "incidents-sample.csv",
      total_records: 100,
      valid_records: 96,
      invalid_records: 4,
      invalid_breakdown: [{ code: "E_STATUS", label: "Estado inválido", count: 4 }],
      category_breakdown: [{ code: "PRODUCT", label: "Producto", count: 50, percentage: 52.1 }],
      status_breakdown: [{ code: "CLOSED", label: "Cerrado", count: 80, percentage: 83.3 }],
      satisfaction: {
        scored_closed_cases: 70,
        total_closed_cases: 80,
        average_score: 4.25,
        score_breakdown: [{ code: "5", label: "5 estrellas", count: 40 }],
      },
    };

    vi.spyOn(incidentsApi, "analyzeIncidentsFile").mockResolvedValue(mockPayload);

    render(<IncidentsAnalyzer />);

    const fileInput = screen.getByLabelElement ? screen.getByLabelElement() : document.querySelector('input[type="file"]')!;
    const file = new File(["test-content"], "incidents-sample.csv", { type: "text/csv" });

    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(screen.getByText("incidents-sample.csv")).toBeInTheDocument();

    const analyzeBtn = screen.getByRole("button", { name: /Analizar incidencias/i });
    fireEvent.click(analyzeBtn);

    await waitFor(() => {
      expect(screen.getByText("Total procesado")).toBeInTheDocument();
      expect(screen.getByText("100")).toBeInTheDocument();
      expect(screen.getByText("96")).toBeInTheDocument();
      expect(screen.getByText("4.25")).toBeInTheDocument();
      expect(screen.getByText("Desglose de registros invalidos")).toBeInTheDocument();
    });

    const downloadBtn = screen.getByRole("button", { name: /Descargar CSV/i });
    expect(downloadBtn).not.toBeDisabled();
  });
});

