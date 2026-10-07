"use client";

/**
 * incidents-results.tsx — Brasaland · Results panel for the incidents analyzer
 *
 * Extracted from `incidents-analyzer.tsx` so it can be code-split and lazily
 * loaded ONLY when an analysis payload exists (users who never run an analysis
 * never download this chunk).
 *
 * The merged/ranked/cumulative highlights table is computed with `useMemo`
 * over the pure `deriveIncidentHighlights` helper — the calculation only runs
 * when `analysis` changes, not on every render of the component.
 */

import { useMemo } from "react";

import { type IncidentAnalysisResponse } from "@/lib/incidents-api";
import {
  countDistinctHighlightCodes,
  deriveIncidentHighlights,
  paretoTopRows,
} from "@/lib/incidents-derive";

function percentageLabel(value?: number | null) {
  return value === undefined || value === null ? null : `${value.toFixed(1)}%`;
}

type IncidentsResultsProps = {
  analysis: IncidentAnalysisResponse;
};

export function IncidentsResults({ analysis }: IncidentsResultsProps) {
  // ── useMemo: cálculo no trivial ─────────────────────────────
  // Merges 4 breakdown tables, sorts them by count (stable tie-break),
  // computes per-table shares and cumulative (Pareto) percentages.
  // Recomputes ONLY when `analysis` identity changes.
  const highlights = useMemo(() => deriveIncidentHighlights(analysis), [analysis]);
  const paretoRows = useMemo(() => paretoTopRows(highlights, 80), [highlights]);
  const distinctCodes = useMemo(() => countDistinctHighlightCodes(highlights), [highlights]);

  return (
    <>
      <section className="kpi-grid incidents-kpis" aria-live="polite">
        <article className="card">
          <h3>Total procesado</h3>
          <p className="kpi-number">{analysis.total_records}</p>
          <p className="kpi-sub">Incluye validos e invalidos</p>
        </article>
        <article className="card">
          <h3>Registros validos</h3>
          <p className="kpi-number kpi-good">{analysis.valid_records}</p>
          <p className="kpi-sub">Base del resumen principal</p>
        </article>
        <article className="card">
          <h3>Registros invalidos</h3>
          <p className="kpi-number kpi-warn">{analysis.invalid_records}</p>
          <p className="kpi-sub">Marcados y excluidos del analisis</p>
        </article>
        <article className="card">
          <h3>Satisfaccion media</h3>
          <p className="kpi-number">{analysis.satisfaction.average_score.toFixed(2)}</p>
          <p className="kpi-sub">Solo casos CLOSED con score</p>
        </article>
      </section>

      <section className="panel-grid incidents-panels">
        <article className="card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Calidad del archivo</p>
              <h3>Desglose de registros invalidos</h3>
            </div>
            <span className="chip chip-danger">{analysis.invalid_records} invalidos</span>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Regla</th>
                <th>Cantidad</th>
              </tr>
            </thead>
            <tbody>
              {analysis.invalid_breakdown.map((item) => (
                <tr key={item.code}>
                  <td>{item.label}</td>
                  <td>{item.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>

        <article className="card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Casos cerrados</p>
              <h3>Indice de satisfaccion</h3>
            </div>
            <span className="chip chip-ok">
              {analysis.satisfaction.scored_closed_cases}/{analysis.satisfaction.total_closed_cases} con score
            </span>
          </div>
          <p className="score-highlight">{analysis.satisfaction.average_score.toFixed(2)} / 5.00</p>
          <table className="table">
            <thead>
              <tr>
                <th>Score</th>
                <th>Etiqueta</th>
                <th>Cantidad</th>
              </tr>
            </thead>
            <tbody>
              {analysis.satisfaction.score_breakdown.map((item) => (
                <tr key={item.code}>
                  <td>{item.code}</td>
                  <td>{item.label}</td>
                  <td>{item.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>

      <section className="panel-grid incidents-panels">
        <article className="card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Distribucion principal</p>
              <h3>Incidencias por categoria</h3>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Categoria</th>
                <th>Cantidad</th>
                <th>Porcentaje</th>
              </tr>
            </thead>
            <tbody>
              {analysis.category_breakdown.map((item) => (
                <tr key={item.code}>
                  <td>{item.label}</td>
                  <td>{item.count}</td>
                  <td>{percentageLabel(item.percentage)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>

        <article className="card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Seguimiento operativo</p>
              <h3>Incidencias por estado</h3>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Estado</th>
                <th>Cantidad</th>
                <th>Porcentaje</th>
              </tr>
            </thead>
            <tbody>
              {analysis.status_breakdown.map((item) => (
                <tr key={item.code}>
                  <td>{item.label}</td>
                  <td>{item.count}</td>
                  <td>{percentageLabel(item.percentage)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </section>

      <section className="card incidents-highlights" data-testid="incidents-highlights">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Ranking consolidado (useMemo)</p>
            <h3>Prioridades consolidadas de incidencias</h3>
          </div>
          <span className="chip chip-ok">
            {distinctCodes} categorias · Pareto 80%: {paretoRows.length} filas
          </span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Origen</th>
              <th>Codigo</th>
              <th>Cantidad</th>
              <th>% de su tabla</th>
              <th>% acumulado</th>
            </tr>
          </thead>
          <tbody>
            {highlights.map((row, index) => (
              <tr key={`${row.source}:${row.code}`}>
                <td>{index + 1}</td>
                <td>{row.source}</td>
                <td>{row.code}</td>
                <td>{row.count}</td>
                <td>{percentageLabel(row.shareOfTable)}</td>
                <td>{percentageLabel(row.cumulativePercentage)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
