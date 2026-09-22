import { AuthGuard } from "@/components/auth-guard";
import { BackofficeHeader } from "@/components/backoffice-header";
import { TelemetryReportDashboard } from "@/components/telemetry/telemetry-report-dashboard";

export const metadata = {
  title: "Telemetría — Brasaland Backoffice",
  description: "Reporte técnico de observabilidad, errores y rendimiento de Brasaland.",
};

export default function BackofficeTelemetryPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="telemetry" badge="Reporte técnico" />

        <main className="container bo-main py-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <TelemetryReportDashboard />
        </main>
      </div>
    </AuthGuard>
  );
}
