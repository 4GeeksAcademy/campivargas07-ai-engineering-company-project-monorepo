import { BackofficeHeader } from '@/components/backoffice-header';
import { AuthGuard } from '@/components/auth-guard';
import { InventoryNav } from '@/components/inventory/inventory-nav';
import { OrdersLedger } from '@/components/inventory/orders-ledger';

export const metadata = {
  title: 'Historial de Órdenes — Brasaland Backoffice',
  description: 'Historial cronológico de movimientos de inventario: entradas y salidas de stock.',
};

export default function InventoryOrdersPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="inventory" badge="Gestión de Inventario" />

        <main className="container bo-main">
          <InventoryNav />
          <OrdersLedger />
        </main>
      </div>
    </AuthGuard>
  );
}
