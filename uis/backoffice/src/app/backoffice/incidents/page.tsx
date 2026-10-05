import { AuthGuard } from "@/components/auth-guard";
import { BackofficeHeader } from "@/components/backoffice-header";
import { IncidentBoard } from "@/components/incidents/IncidentBoard";

export const metadata = {
  title: "Incidencias — Brasaland Backoffice",
  description: "Gestor interno protegido de incidencias operativas de Brasaland.",
};

export default function BackofficeIncidentsPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="incidents" badge="Gestor de incidencias" />

        <main className="container bo-main">
          <IncidentBoard />
        </main>
      </div>
    </AuthGuard>
  );
}
