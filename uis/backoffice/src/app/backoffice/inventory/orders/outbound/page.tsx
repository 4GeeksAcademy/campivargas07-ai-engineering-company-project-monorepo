import React, { Suspense } from 'react';
import { BackofficeHeader } from '@/components/backoffice-header';
import { AuthGuard } from '@/components/auth-guard';
import { InventoryNav } from '@/components/inventory/inventory-nav';
import { OutboundOrderForm } from '@/components/inventory/outbound-order-form';

export const metadata = {
  title: 'Salida de Stock — Brasaland Backoffice',
  description: 'Registro de órdenes de salida y consumo de ingredientes en sede.',
};

export default function OutboundOrderPage() {
  return (
    <div className="backoffice-page">
      <BackofficeHeader activeView="inventory" badge="Gestión de Inventario" />

      <main className="container bo-main">
        <AuthGuard>
          <InventoryNav />
          <Suspense fallback={<div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>Cargando formulario de salida...</div>}>
            <OutboundOrderForm />
          </Suspense>
        </AuthGuard>
      </main>
    </div>
  );
}
