import dynamic from "next/dynamic";

import { AuthGuard } from "@/components/auth-guard";
import { BackofficeHeader } from "@/components/backoffice-header";

/**
 * Lazy loading (task spec, Phase 2 — componente/ruta #1):
 * `IncidentsAnalyzer` (cliente, ~14 KB + dependencias) se importa de forma
 * dinámica desde esta Server Component. Next.js genera un chunk aparte y lo
 * descarga en paralelo tras el HTML, con un fallback accesible mientras llega.
 * `ssr: false` NO se usa (no está permitido en Server Components y no hace
 * falta: el upload no depende del DOM del servidor).
 */
const IncidentsAnalyzer = dynamic(
  () => import("@/components/incidents-analyzer").then((mod) => mod.IncidentsAnalyzer),
  {
    loading: () => (
      <div className="container bo-main" role="status" aria-live="polite">
        <section className="card empty-state">
          <p className="eyebrow">Cargando módulo</p>
          <h3>Preparando el analizador de incidencias…</h3>
          <p className="muted">Descargando el módulo de análisis bajo demanda.</p>
        </section>
      </div>
    ),
  },
);

export const metadata = {
  title: "Incidencias — Brasaland Backoffice",
  description: "Analizador interno protegido para incidencias operativas de Brasaland.",
};

export default function BackofficeIncidentsPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="incidents" badge="Incidents analysis online" />

        <main className="container bo-main">
          <IncidentsAnalyzer />
        </main>
      </div>
    </AuthGuard>
  );
}
