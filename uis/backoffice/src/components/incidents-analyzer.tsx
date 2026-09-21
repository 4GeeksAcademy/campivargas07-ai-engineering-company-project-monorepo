"use client";

/**
 * incidents-analyzer.tsx — Brasaland · Incidents analyzer (upload + orchestration)
 *
 * Lazy loading (task spec, Phase 2):
 * - This component itself is dynamically imported by the /incidents server
 *   page via `next/dynamic` (see src/app/backoffice/incidents/page.tsx).
 * - The heavy results panel (`IncidentsResults`) is ALSO code-split from here:
 *   its chunk downloads only when an analysis exists, with an inline fallback.
 * - `next/dynamic` without `ssr: false` works in both server and client
 *   components (React.lazy + Suspense under the hood).
 */

import { ChangeEvent, DragEvent, useId, useState, useTransition } from "react";
import dynamic from "next/dynamic";

import { analyzeIncidentsFile, getIncidentsExportUrl, type IncidentAnalysisResponse } from "@/lib/incidents-api";

// Lazy-loaded results panel: downloaded only when `analysis` is set.
// The `loading` fallback keeps the UI responsive while the chunk arrives.
const IncidentsResults = dynamic(
  () => import("@/components/incidents-results").then((mod) => mod.IncidentsResults),
  {
    loading: () => (
      <section className="card empty-state" role="status" aria-live="polite">
        <p className="eyebrow">Preparando resultados</p>
        <h3>Cargando panel de resultados…</h3>
        <p className="muted">El análisis terminó; estamos cargando el resumen visual.</p>
      </section>
    ),
  },
);

export function IncidentsAnalyzer() {
  const inputId = useId();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<IncidentAnalysisResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPending, startTransition] = useTransition();

  function onFileSelected(file: File | null) {
    setSelectedFile(file);
    setErrorMessage(null);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    onFileSelected(event.target.files?.[0] ?? null);
  }

  function handleDragOver(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0] ?? null;
    onFileSelected(file);
  }

  async function handleAnalyze() {
    if (!selectedFile) {
      setErrorMessage("Selecciona un archivo CSV antes de analizar.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const payload = await analyzeIncidentsFile(selectedFile);
      startTransition(() => {
        setAnalysis(payload);
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo completar el analisis.";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleDownload() {
    const link = document.createElement("a");
    link.href = getIncidentsExportUrl();
    link.download = "results.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  const busy = isSubmitting || isPending;

  return (
    <div className="incidents-layout">
      <section className="card incidents-hero">
        <div>
          <p className="eyebrow">Analisis operativo interno</p>
          <h2>Sube el CSV de incidencias y obtén el resumen validado al instante</h2>
          <p className="muted incidents-copy">
            El archivo se procesa internamente contra las reglas exactas del contexto de Brasaland: campos esperados, categorias validas, estados permitidos y control de registros incompletos.
          </p>
        </div>

        <div className="hero-metrics">
          <div>
            <span>Campos auditados</span>
            <strong>9</strong>
          </div>
          <div>
            <span>Estados permitidos</span>
            <strong>3</strong>
          </div>
          <div>
            <span>Categorias validas</span>
            <strong>5</strong>
          </div>
        </div>
      </section>

      <section className="card upload-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Carga de archivo</p>
            <h3>Selecciona o arrastra un CSV</h3>
          </div>
          <span className="chip chip-ok">POST /api/incidents/analyze</span>
        </div>

        <label
          className={isDragging ? "upload-zone upload-zone-active" : "upload-zone"}
          htmlFor={inputId}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <input accept=".csv,text/csv" className="sr-only" id={inputId} onChange={handleInputChange} type="file" />
          <span className="upload-title">Arrastra el archivo aquí o selecciónalo desde tu equipo</span>
          <span className="muted">Se acepta CSV UTF-8 con encabezados de Brasaland.</span>
          <strong>{selectedFile ? selectedFile.name : "Ningun archivo seleccionado"}</strong>
        </label>

        <div className="actions-row">
          <button className="primary-button" disabled={busy} onClick={handleAnalyze} type="button">
            {busy ? "Analizando..." : "Analizar incidencias"}
          </button>
          <button className="secondary-button" disabled={!analysis || busy} onClick={handleDownload} type="button">
            Descargar CSV
          </button>
        </div>

        {errorMessage ? <p className="feedback feedback-error">{errorMessage}</p> : null}
        {!errorMessage && analysis ? (
          <p className="feedback feedback-ok">
            Analisis disponible para {analysis.source_file}. Registros invalidos detectados: {analysis.invalid_records}.
          </p>
        ) : null}
      </section>

      {analysis ? (
        <IncidentsResults analysis={analysis} />
      ) : (
        <section className="card empty-state">
          <p className="eyebrow">Pendiente de analisis</p>
          <h3>No hay resultados cargados todavia</h3>
          <p className="muted">
            Sube un archivo para ver el resumen de validacion, el desglose por categoria, el estado de los casos y el indice de satisfaccion.
          </p>
        </section>
      )}
    </div>
  );
}