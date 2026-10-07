import { AuthGuard } from "@/components/auth-guard";
import { BackofficeHeader } from "@/components/backoffice-header";
import { InventoryHealthDashboard } from "@/components/reporting/inventory-health-dashboard";

export const metadata = {
  title: "Salud de Inventario — Brasaland Backoffice",
  description: "Dashboard analítico de salud de inventario, stockout y KPIs para la Dirección de Operaciones.",
};

export default function BackofficeInventoryHealthPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="reporting" badge="Salud Operativa" />

        <main className="container bo-main py-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <InventoryHealthDashboard />
        </main>
      </div>
    </AuthGuard>
  );
}
