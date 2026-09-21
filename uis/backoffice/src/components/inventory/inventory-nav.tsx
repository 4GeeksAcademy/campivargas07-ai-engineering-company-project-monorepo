'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface NavItem {
  href: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: '/backoffice/inventory/products', label: 'Productos y Stock' },
  { href: '/backoffice/inventory/orders/inbound', label: 'Registrar Entrada' },
  { href: '/backoffice/inventory/orders/outbound', label: 'Registrar Salida' },
  { href: '/backoffice/inventory/orders', label: 'Historial de Órdenes' },
];

export function InventoryNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Navegación del módulo de inventario"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.5rem',
        marginBottom: '1.25rem',
        padding: '0.35rem',
        background: 'rgba(255, 255, 255, 0.03)',
        borderRadius: '999px',
        border: '1px solid var(--border)',
        width: 'fit-content',
      }}
    >
      {NAV_ITEMS.map((item) => {
        const isActive =
          item.href === '/backoffice/inventory/orders'
            ? pathname === item.href
            : pathname.startsWith(item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={isActive ? 'nav-link nav-link-active' : 'nav-link'}
            style={{
              fontSize: '0.86rem',
              fontWeight: isActive ? 700 : 500,
            }}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

