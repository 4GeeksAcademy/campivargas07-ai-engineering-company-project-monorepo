'use client';

import React, { useEffect, useState, useTransition } from 'react';
import Link from 'next/link';
import {
  RESTAURANT_LOCATIONS,
  RESTAURANT_STORAGE_KEY,
  getRestaurantLabel,
} from '@/lib/constants/restaurants';
import { inventoryApi, type InventoryOrder } from '@/lib/inventory';

export function OrdersLedger() {
  const [selectedRestaurant, setSelectedRestaurant] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(RESTAURANT_STORAGE_KEY);
      if (saved && RESTAURANT_LOCATIONS.some((r) => r.id === saved)) {
        return saved;
      }
    }
    return 'ALL';
  });
  const [selectedType, setSelectedType] = useState<'ALL' | 'inbound' | 'outbound'>('ALL');
  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const loadOrders = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters = {
        local_id: selectedRestaurant !== 'ALL' ? selectedRestaurant : undefined,
        type: selectedType !== 'ALL' ? selectedType : undefined,
      };
      const data = await inventoryApi.listOrders(filters);
      startTransition(() => {
        setOrders(data.orders);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar historial de movimientos');
    } finally {
      setLoading(false);
    }
  }, [selectedRestaurant, selectedType]);

  useEffect(() => {
    let isMounted = true;

    const filters = {
      local_id: selectedRestaurant !== 'ALL' ? selectedRestaurant : undefined,
      type: selectedType !== 'ALL' ? selectedType : undefined,
    };

    inventoryApi
      .listOrders(filters)
      .then((data) => {
        if (isMounted) {
          startTransition(() => {
            setOrders(data.orders);
            setError(null);
            setLoading(false);
          });
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Error al cargar historial de movimientos');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [selectedRestaurant, selectedType]);

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleString('es-CO', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="card" style={{ display: 'grid', gap: '1.25rem' }}>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.35rem', marginBottom: '0.2rem' }}>Historial de Movimientos de Inventario</h2>
          <p style={{ color: 'var(--muted)', fontSize: '0.86rem' }}>
            Registro inmutable de entradas, salidas y trazabilidad de operaciones (solo lectura)
          </p>
        </div>

        {/* Filters */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.8rem', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <label htmlFor="ledger-local-filter" style={{ fontSize: '0.82rem', color: 'var(--muted)', fontWeight: 600 }}>
              Sede:
            </label>
            <select
              id="ledger-local-filter"
              value={selectedRestaurant}
              onChange={(e) => {
                setSelectedRestaurant(e.target.value);
                setLoading(true);
              }}
              style={{
                padding: '0.4rem 0.75rem',
                borderRadius: '0.5rem',
                background: '#07111f',
                border: '1px solid var(--border)',
                color: 'var(--fg)',
                fontSize: '0.86rem',
                outline: 'none',
              }}
            >
              <option value="ALL">Todas las sedes</option>
              {RESTAURANT_LOCATIONS.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.nombre} ({loc.id})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <label htmlFor="ledger-type-filter" style={{ fontSize: '0.82rem', color: 'var(--muted)', fontWeight: 600 }}>
              Tipo:
            </label>
            <select
              id="ledger-type-filter"
              value={selectedType}
              onChange={(e) => {
                setSelectedType(e.target.value as 'ALL' | 'inbound' | 'outbound');
                setLoading(true);
              }}
              style={{
                padding: '0.4rem 0.75rem',
                borderRadius: '0.5rem',
                background: '#07111f',
                border: '1px solid var(--border)',
                color: 'var(--fg)',
                fontSize: '0.86rem',
                outline: 'none',
              }}
            >
              <option value="ALL">Todos los tipos</option>
              <option value="inbound">Entradas (+)</option>
              <option value="outbound">Salidas (-)</option>
            </select>
          </div>
        </div>
      </div>

      {loading && (
        <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--muted)' }} aria-live="polite">
          Cargando historial de órdenes...
        </div>
      )}

      {error && !loading && (
        <div className="feedback feedback-error" role="alert" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{error}</span>
          <button
            type="button"
            className="secondary-button"
            onClick={loadOrders}
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem' }}
          >
            Reintentar
          </button>
        </div>
      )}

      {!loading && !error && orders.length === 0 && (
        <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: 'var(--muted)', display: 'grid', gap: '0.85rem', justifyItems: 'center' }}>
          <p>No se encontraron órdenes para la sede o filtro seleccionado.</p>
          <div style={{ display: 'flex', gap: '0.6rem' }}>
            <Link
              href="/backoffice/inventory/orders/inbound"
              className="primary-button"
              style={{ padding: '0.45rem 0.85rem', fontSize: '0.84rem', textDecoration: 'none' }}
            >
              + Registrar entrada
            </Link>
            <Link
              href="/backoffice/inventory/orders/outbound"
              className="secondary-button"
              style={{ padding: '0.45rem 0.85rem', fontSize: '0.84rem', textDecoration: 'none' }}
            >
              - Registrar salida
            </Link>
          </div>
        </div>
      )}

      {!loading && !error && orders.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', minWidth: '780px' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'center', width: '130px' }}>Tipo</th>
                <th style={{ textAlign: 'left' }}>SKU</th>
                <th style={{ textAlign: 'left' }}>Ingrediente</th>
                <th style={{ textAlign: 'left' }}>Sede</th>
                <th style={{ textAlign: 'right' }}>Cantidad</th>
                <th style={{ textAlign: 'left' }}>Fecha y Hora</th>
                <th style={{ textAlign: 'left' }}>Usuario (UUID)</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((item) => {
                const isInbound = item.type === 'inbound';
                return (
                  <tr key={item.id}>
                    <td style={{ textAlign: 'center' }}>
                      <span className={isInbound ? 'chip chip-ok' : 'chip chip-danger'} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <span>{isInbound ? '📥' : '📤'}</span>
                        <span>{isInbound ? 'ENTRADA' : 'SALIDA'}</span>
                      </span>
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--muted)' }}>{item.ingredient_sku}</td>
                    <td style={{ fontWeight: 600 }}>{item.ingredient_name}</td>
                    <td style={{ fontSize: '0.88rem' }}>{getRestaurantLabel(item.local_id)}</td>
                    <td
                      style={{
                        textAlign: 'right',
                        fontWeight: 700,
                        fontVariantNumeric: 'tabular-nums',
                        color: isInbound ? 'var(--ok)' : 'var(--danger)',
                      }}
                    >
                      {isInbound ? `+${item.quantity}` : `-${item.quantity}`}
                    </td>
                    <td style={{ color: 'var(--muted)', fontSize: '0.86rem' }}>
                      {formatDate(item.created_at)}
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--muted)' }}>
                      {item.user_uuid}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
