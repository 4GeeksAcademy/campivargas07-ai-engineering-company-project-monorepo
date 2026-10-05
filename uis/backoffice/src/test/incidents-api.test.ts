import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  analyzeIncidentsFile,
  analyzeIncidentsText,
  createIncident,
  getIncidentsExportUrl,
  getIncidentsSummary,
  listIncidents,
  updateIncidentStatus,
  type Incident,
  type IncidentAnalysisResponse,
} from "@/lib/incidents-api";
import { authApi } from "@/lib/auth";

describe("incidents-api client library", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    authApi.setToken(null);
  });

  afterEach(() => {
    authApi.setToken(null);
    vi.unstubAllGlobals();
  });

  it("listIncidents sends filters and the bearer token through the Next proxy", async () => {
    const incidents: Incident[] = [];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => incidents,
    });
    vi.stubGlobal("fetch", fetchMock);
    authApi.setToken("test-token");

    await expect(listIncidents({ status: "open", branch: "COL-01" })).resolves.toEqual(incidents);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/api/incidents?status=open&branch=COL-01",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
  });

  it("createIncident and updateIncidentStatus use the manager write contract", async () => {
    const incident = {
      id: "INC-001",
      title: "Falla de equipo",
      description: "La parrilla no enciende",
      category: "EQUIPMENT",
      branch: "COL-01",
      origin: "manual",
      status: "open",
      reported_at: "2026-09-21T00:00:00Z",
      updated_at: "2026-09-21T00:00:00Z",
    } satisfies Incident;
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 201, json: async () => incident })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ ...incident, status: "in_progress" }),
      });
    vi.stubGlobal("fetch", fetchMock);

    await createIncident({
      title: incident.title,
      description: incident.description,
      category: incident.category,
      branch: incident.branch,
    });
    await updateIncidentStatus(incident.id, { status: "in_progress" });

    expect(fetchMock.mock.calls[0]).toEqual([
      "/api/api/incidents",
      expect.objectContaining({ method: "POST" }),
    ]);
    expect(fetchMock.mock.calls[1]).toEqual([
      "/api/api/incidents/INC-001/status",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ status: "in_progress" }),
      }),
    ]);
  });

  it("getIncidentsSummary exposes API error messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ message: "No se pudo calcular el resumen" }),
    }));

    await expect(getIncidentsSummary()).rejects.toThrow("No se pudo calcular el resumen");
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
    expect(fetchMock.mock.calls[0][0]).toBe("/api/api/incidents/analyze");
    expect(result).toEqual(mockData);
  });

  it("analyzeIncidentsText converts pasted CSV into an uploaded file", async () => {
    const mockData: IncidentAnalysisResponse = {
      source_file: "pasted.csv",
      total_records: 1,
      valid_records: 1,
      invalid_records: 0,
      invalid_breakdown: [],
      category_breakdown: [],
      status_breakdown: [],
      satisfaction: {
        scored_closed_cases: 0,
        total_closed_cases: 0,
        average_score: 0,
        score_breakdown: [],
      },
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(analyzeIncidentsText("id,status\n1,OPEN", "pasted.csv")).resolves.toEqual(mockData);
    const body = fetchMock.mock.calls[0][1]?.body as FormData;
    expect((body.get("file") as File).name).toBe("pasted.csv");
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
