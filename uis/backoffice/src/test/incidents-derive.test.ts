import { describe, it, expect } from "vitest";

import {
  countDistinctHighlightCodes,
  deriveIncidentHighlights,
  paretoTopRows,
} from "@/lib/incidents-derive";
import type { IncidentAnalysisResponse } from "@/lib/incidents-api";

function buildAnalysis(overrides: Partial<IncidentAnalysisResponse> = {}): IncidentAnalysisResponse {
  return {
    source_file: "incidents-sample.csv",
    total_records: 100,
    valid_records: 96,
    invalid_records: 4,
    invalid_breakdown: [
      { code: "E_STATUS", label: "Estado inválido", count: 3 },
      { code: "E_CATEGORY", label: "Categoría inválida", count: 1 },
    ],
    category_breakdown: [
      { code: "PRODUCT", label: "Producto", count: 50, percentage: 52.1 },
      { code: "SERVICE", label: "Servicio", count: 46, percentage: 47.9 },
    ],
    status_breakdown: [
      { code: "CLOSED", label: "Cerrado", count: 80, percentage: 83.3 },
      { code: "OPEN", label: "Abierto", count: 16, percentage: 16.7 },
    ],
    satisfaction: {
      scored_closed_cases: 70,
      total_closed_cases: 80,
      average_score: 4.25,
      score_breakdown: [
        { code: "5", label: "5 estrellas", count: 40 },
        { code: "4", label: "4 estrellas", count: 30 },
      ],
    },
    ...overrides,
  };
}

describe("deriveIncidentHighlights", () => {
  it("merges all four tables into one ranked list sorted by count desc", () => {
    const rows = deriveIncidentHighlights(buildAnalysis());

    expect(rows).toHaveLength(8); // 2 + 2 + 2 + 2
    expect(rows[0]).toMatchObject({ source: "status", code: "CLOSED", count: 80 });
    expect(rows[1]).toMatchObject({ source: "category", code: "PRODUCT", count: 50 });
    expect(rows[2]).toMatchObject({ source: "category", code: "SERVICE", count: 46 });
    expect(rows[3]).toMatchObject({ source: "score", code: "5", count: 40 });
    // Stable tie-break: same count -> code ascending
    const ties = rows.filter((r) => r.count === 46);
    expect(ties.map((r) => r.code)).toEqual(["SERVICE"]);

    const counts = rows.map((r) => r.count);
    const sorted = [...counts].sort((a, b) => b - a);
    expect(counts).toEqual(sorted);
  });

  it("computes cumulative percentages that reach 100 at the last row", () => {
    const rows = deriveIncidentHighlights(buildAnalysis());
    const grandTotal = rows.reduce((sum, r) => sum + r.count, 0);
    expect(grandTotal).toBe(80 + 40 + 50 + 46 + 3 + 1 + 30 + 16);

    const last = rows[rows.length - 1];
    expect(last.cumulativePercentage).toBeCloseTo(100, 1);
    // Cumulative is non-decreasing
    for (let i = 1; i < rows.length; i += 1) {
      expect(rows[i].cumulativePercentage).toBeGreaterThanOrEqual(rows[i - 1].cumulativePercentage);
    }
  });

  it("computes per-table shares relative to each source table", () => {
    const rows = deriveIncidentHighlights(buildAnalysis());

    const closed = rows.find((r) => r.source === "status" && r.code === "CLOSED");
    expect(closed?.shareOfTable).toBe(83.3); // 80 / 96

    const fiveStars = rows.find((r) => r.source === "score" && r.code === "5");
    expect(fiveStars?.shareOfTable).toBe(57.1); // 40 / 70
  });

  it("is pure: the same input yields equal output and input is not mutated", () => {
    const analysis = buildAnalysis();
    const snapshot = JSON.stringify(analysis);

    const rows1 = deriveIncidentHighlights(analysis);
    const rows2 = deriveIncidentHighlights(analysis);

    expect(rows1).toEqual(rows2);
    expect(JSON.stringify(analysis)).toBe(snapshot); // no mutation -> safe for useMemo deps
  });

  it("ignores zero/negative counts and empty tables gracefully", () => {
    const rows = deriveIncidentHighlights(
      buildAnalysis({
        invalid_breakdown: [{ code: "E_ZERO", label: "Cero", count: 0 }],
        category_breakdown: [],
      }),
    );

    expect(rows.find((r) => r.code === "E_ZERO")).toBeUndefined();
    expect(rows.find((r) => r.source === "category")).toBeUndefined();
    expect(rows.length).toBeGreaterThan(0);
  });

  it("handles an entirely empty analysis without dividing by zero", () => {
    const rows = deriveIncidentHighlights(
      buildAnalysis({
        invalid_breakdown: [],
        category_breakdown: [],
        status_breakdown: [],
        satisfaction: {
          scored_closed_cases: 0,
          total_closed_cases: 0,
          average_score: 0,
          score_breakdown: [],
        },
      }),
    );
    expect(rows).toEqual([]);
  });
});

describe("countDistinctHighlightCodes", () => {
  it("dedupes by source+code", () => {
    const rows = deriveIncidentHighlights(buildAnalysis());
    expect(countDistinctHighlightCodes(rows)).toBe(8);
  });
});

describe("paretoTopRows", () => {
  it("returns the smallest prefix covering the threshold", () => {
    const rows = deriveIncidentHighlights(buildAnalysis());
    const top = paretoTopRows(rows, 80);

    // Every row except the last must be below the threshold.
    top.slice(0, -1).forEach((row) => expect(row.cumulativePercentage).toBeLessThan(80));
    expect(top[top.length - 1].cumulativePercentage).toBeGreaterThanOrEqual(80);
    expect(top.length).toBeLessThan(rows.length);
  });

  it("returns all rows when threshold is 100", () => {
    const rows = deriveIncidentHighlights(buildAnalysis());
    expect(paretoTopRows(rows, 100)).toHaveLength(rows.length);
  });

  it("returns empty for empty input", () => {
    expect(paretoTopRows([], 80)).toEqual([]);
  });
});
