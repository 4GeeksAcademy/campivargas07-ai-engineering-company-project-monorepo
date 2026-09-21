import { AuthGuard } from "@/components/auth-guard";
import { BackofficeHeader } from "@/components/backoffice-header";
import { IncidentsAnalyzer } from "@/components/incidents-analyzer";

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
