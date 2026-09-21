/**
 * incidents-derive.ts — Brasaland · Pure derivations for the incidents analyzer
 *
 * Pure functions (no I/O, no React) extracted so that:
 * 1. They are unit-testable in isolation (vitest, no jsdom needed).
 * 2. The results panel can wrap them in `useMemo` and only recompute when the
 *    underlying analysis payload changes, not on every render.
 *
 * Non-trivial work performed (per task spec: "cálculo no trivial"):
 * - Merges the 4 breakdown tables into a single ranked view.
 * - Sorts by descending count with a stable tie-break (code ascending).
 * - Computes each row's percentage of the valid total and the cumulative
 *   percentage (Pareto-style running total).
 */

import type { BreakdownItem, IncidentAnalysisResponse } from "@/lib/incidents-api";

export type DerivedRow = {
  source: "invalid" | "category" | "status" | "score";
  code: string;
  label: string;
  count: number;
  /** Share of the row's count vs the total of its own table (0–100, 1 decimal). */
  shareOfTable: number | null;
  /** Running cumulative percentage within the merged ranking (0–100, 1 decimal). */
  cumulativePercentage: number;
};

function normalizeRows(items: BreakdownItem[]): { code: string; label: string; count: number }[] {
  return items
    .filter((item) => Number.isFinite(item.count) && item.count > 0)
    .map((item) => ({
      code: item.code,
      label: item.label,
      count: item.count,
    }));
}

/**
 * Build the merged, ranked, cumulative-percentage view across all four
 * breakdown tables of an analysis payload.
 */
export function deriveIncidentHighlights(
  analysis: IncidentAnalysisResponse,
): DerivedRow[] {
  const sources: Array<{
    source: DerivedRow["source"];
    items: BreakdownItem[];
  }> = [
    { source: "invalid", items: analysis.invalid_breakdown },
    { source: "category", items: analysis.category_breakdown },
    { source: "status", items: analysis.status_breakdown },
    { source: "score", items: analysis.satisfaction.score_breakdown },
  ];

  const tableTotals = new Map<DerivedRow["source"], number>();
  const collected: Array<DerivedRow & { _sortCount: number }> = [];

  for (const { source, items } of sources) {
    const rows = normalizeRows(items);
    const tableTotal = rows.reduce((sum, row) => sum + row.count, 0);
    tableTotals.set(source, tableTotal);
    for (const row of rows) {
      collected.push({
        source,
        code: row.code,
        label: row.label,
        count: row.count,
        shareOfTable: tableTotal > 0 ? round1((row.count / tableTotal) * 100) : null,
        cumulativePercentage: 0,
        _sortCount: row.count,
      });
    }
  }

  // Stable sort: count desc, then code asc (deterministic output for tests).
  collected.sort((a, b) => b._sortCount - a._sortCount || a.code.localeCompare(b.code));

  const grandTotal = collected.reduce((sum, row) => sum + row.count, 0);
  let running = 0;
  const result: DerivedRow[] = collected.map(({ _sortCount, ...row }) => {
    running += _sortCount;
    return {
      ...row,
      cumulativePercentage: grandTotal > 0 ? round1((running / grandTotal) * 100) : 0,
    };
  });

  return result;
}

/** Number of categories represented in the merged view (dedup by source+code). */
export function countDistinctHighlightCodes(rows: DerivedRow[]): number {
  const seen = new Set(rows.map((row) => `${row.source}:${row.code}`));
  return seen.size;
}

/** The rows that together account for the first `threshold`% of incidents (Pareto cut). */
export function paretoTopRows(rows: DerivedRow[], threshold = 80): DerivedRow[] {
  if (rows.length === 0) return [];
  const top: DerivedRow[] = [];
  for (const row of rows) {
    top.push(row);
    if (row.cumulativePercentage >= threshold) break;
  }
  return top;
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}
