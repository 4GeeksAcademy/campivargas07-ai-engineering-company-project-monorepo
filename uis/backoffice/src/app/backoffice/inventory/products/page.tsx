import { BackofficeHeader } from '@/components/backoffice-header';
import { AuthGuard } from '@/components/auth-guard';
import { InventoryNav } from '@/components/inventory/inventory-nav';
import { ProductsTable } from '@/components/inventory/products-table';

export const metadata = {
  title: 'Productos y Stock — Brasaland Backoffice',
  description: 'Gestión de catálogo y monitoreo de inventario en tiempo real por local.',
};

export default function InventoryProductsPage() {
  return (
    <div className="backoffice-page">
      <BackofficeHeader activeView="inventory" badge="Gestión de Inventario" />

      <main className="container bo-main">
        <AuthGuard>
          <InventoryNav />
          <ProductsTable />
        </AuthGuard>
      </main>
    </div>
  );
}
