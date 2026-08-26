import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { analyzeIncidentsFile, getIncidentsExportUrl, type IncidentAnalysisResponse } from "@/lib/incidents-api";

describe("incidents-api client library", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getIncidentsExportUrl returns the correct export URL", () => {
    const url = getIncidentsExportUrl();
    expect(url).toContain("/api/incidents/results/export");
  });

  it("analyzeIncidentsFile successfully sends FormData and parses response", async () => {
    const mockData: IncidentAnalysisResponse = {
      source_file: "test.csv",
      total_records: 10,
      valid_records: 9,
      invalid_records: 1,
      invalid_breakdown: [{ code: "E01", label: "Bad format", count: 1 }],
      category_breakdown: [{ code: "CAT", label: "Category", count: 9 }],
      status_breakdown: [{ code: "OPEN", label: "Open", count: 9 }],
      satisfaction: {
        scored_closed_cases: 5,
        total_closed_cases: 5,
        average_score: 4.5,
        score_breakdown: [{ code: "5", label: "5 estrellas", count: 5 }],
      },
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["dummy,header\n1,2"], "test.csv", { type: "text/csv" });
    const result = await analyzeIncidentsFile(file);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(result).toEqual(mockData);
  });

  it("analyzeIncidentsFile throws server error detail when response is not ok", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: {
        get: (header: string) => (header.toLowerCase() === "content-type" ? "application/json" : null),
      },
      json: async () => ({ detail: "El archivo CSV está vacío." }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File([""], "empty.csv", { type: "text/csv" });

    await expect(analyzeIncidentsFile(file)).rejects.toThrow("El archivo CSV está vacío.");
  });

  it("analyzeIncidentsFile throws fallback message when response is not JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: {
        get: () => "text/plain",
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["data"], "test.csv", { type: "text/csv" });

    await expect(analyzeIncidentsFile(file)).rejects.toThrow("No se pudo analizar el archivo (500).");
  });
});

