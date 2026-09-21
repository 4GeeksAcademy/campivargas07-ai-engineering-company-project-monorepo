import { AuthGuard } from "@/components/auth-guard";
import { BackofficeHeader } from "@/components/backoffice-header";
import { SuppliersDirectory } from "@/components/suppliers-directory";

export const metadata = {
  title: "Proveedores — Brasaland Backoffice",
  description: "Directorio interno protegido de proveedores de Brasaland.",
};

export default function BackofficeSuppliersPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="suppliers" badge="Supplier directory online" />

        <main className="container bo-main">
          <SuppliersDirectory />
        </main>
      </div>
    </AuthGuard>
  );
}
