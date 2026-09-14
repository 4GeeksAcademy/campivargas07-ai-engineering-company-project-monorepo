import React, { Suspense } from 'react';
import { BackofficeHeader } from '@/components/backoffice-header';
import { AuthGuard } from '@/components/auth-guard';
import { InventoryNav } from '@/components/inventory/inventory-nav';
import { InboundOrderForm } from '@/components/inventory/inbound-order-form';

export const metadata = {
  title: 'Entrada de Stock — Brasaland Backoffice',
  description: 'Registro de órdenes de entrada y recepción de insumos en inventario.',
};

export default function InboundOrderPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="inventory" badge="Gestión de Inventario" />

        <main className="container bo-main">
          <InventoryNav />
          <Suspense fallback={<div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>Cargando formulario de entrada...</div>}>
            <InboundOrderForm />
          </Suspense>
        </main>
      </div>
    </AuthGuard>
  );
}
