'use client';

import React, { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import {
  RESTAURANT_LOCATIONS,
  DEFAULT_RESTAURANT_ID,
  RESTAURANT_STORAGE_KEY,
  getRestaurantLabel,
} from '@/lib/constants/restaurants';
import { inventoryApi, type IngredientWithStock } from '@/lib/inventory';
import { RestaurantSelect } from './restaurant-select';
import { telemetryService } from '@/services/telemetry';

export function ProductsTable() {
  const [selectedRestaurant, setSelectedRestaurant] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(RESTAURANT_STORAGE_KEY);
      if (saved && RESTAURANT_LOCATIONS.some((r) => r.id === saved)) {
        return saved;
      }
    }
    return DEFAULT_RESTAURANT_ID;
  });
  const [products, setProducts] = useState<IngredientWithStock[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = React.useCallback(async (localId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await inventoryApi.listProducts(localId);
      setProducts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar productos de inventario');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;

    inventoryApi
      .listProducts(selectedRestaurant)
      .then((data) => {
        if (!ignore) {
          setProducts(data);
          setError(null);
          setLoading(false);

          // Track catalog viewed event
          try {
            const lowStockCount = data.filter((p) => p.current_stock > 0 && p.current_stock <= p.minimum_stock).length;
            const depletedCount = data.filter((p) => p.current_stock <= 0).length;
            telemetryService.track('inventory_catalog_viewed', {
              local_id: selectedRestaurant,
              total_items_rendered: data.length,
              low_stock_items_count: lowStockCount,
              depleted_items_count: depletedCount,
            });
          } catch {
            // Non-blocking
          }
        }
      })
      .catch((err) => {
        if (!ignore) {
          setError(err instanceof Error ? err.message : 'Error al cargar productos de inventario');
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [selectedRestaurant]);

  const filterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleRestaurantChange = (newId: string) => {
    setLoading(true);
    setError(null);
    setSelectedRestaurant(newId);
    localStorage.setItem(RESTAURANT_STORAGE_KEY, newId);

    // Debounced filter event (500 ms) as specified in telemetry plan
    if (filterTimerRef.current) {
      clearTimeout(filterTimerRef.current);
    }
    filterTimerRef.current = setTimeout(() => {
      try {
        telemetryService.track('inventory_filter_applied', {
          local_id: newId,
          category_filter: 'all',
          search_term_length: 0,
          results_count: products.length,
        });
      } catch {
        // Non-blocking
      }
    }, 500);
  };

  const renderStockBadge = (current: number, min: number) => {
    if (current <= 0) {
      return <span className="chip chip-danger">Agotado</span>;
    }
    if (current <= min) {
      return <span className="chip chip-warn">Stock bajo</span>;
    }
    return <span className="chip chip-ok">Saludable</span>;
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
          <h2 style={{ fontSize: '1.35rem', marginBottom: '0.2rem' }}>Catálogo de Ingredientes y Stock</h2>
          <p style={{ color: 'var(--muted)', fontSize: '0.86rem' }}>
            Monitoreo en tiempo real del saldo disponible y alertas operativas por sede
          </p>
        </div>

        <RestaurantSelect
            id="restaurant-select"
            label="Restaurante"
            value={selectedRestaurant}
            onValueChange={handleRestaurantChange}
          />
      </div>

      {loading && (
        <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--muted)' }} aria-live="polite">
          Cargando inventario para sede {getRestaurantLabel(selectedRestaurant)}...
        </div>
      )}

      {error && !loading && (
        <div className="feedback feedback-error" role="alert" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{error}</span>
          <button
            type="button"
            className="secondary-button"
            onClick={() => loadProducts(selectedRestaurant)}
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem' }}
          >
            Reintentar
          </button>
        </div>
      )}

      {!loading && !error && products.length === 0 && (
        <div style={{ padding: '2.5rem 1rem', textAlign: 'center', color: 'var(--muted)', display: 'grid', gap: '0.85rem', justifyItems: 'center' }}>
          <p>No se encontraron ingredientes registrados para la sede {getRestaurantLabel(selectedRestaurant)}.</p>
          <Link
            href={`/backoffice/inventory/orders/inbound?local_id=${selectedRestaurant}`}
            className="primary-button"
            style={{ padding: '0.5rem 1rem', fontSize: '0.88rem', textDecoration: 'none' }}
          >
            + Registrar primera entrada
          </Link>
        </div>
      )}

      {!loading && !error && products.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', minWidth: '700px' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>SKU</th>
                <th style={{ textAlign: 'left' }}>Ingrediente</th>
                <th style={{ textAlign: 'left' }}>Categoría</th>
                <th style={{ textAlign: 'right' }}>Mínimo</th>
                <th style={{ textAlign: 'right' }}>Stock Actual</th>
                <th style={{ textAlign: 'center' }}>Estado</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {products.map((item) => (
                <tr key={item.id}>
                  <td style={{ fontWeight: 600, color: 'var(--muted)' }}>{item.sku}</td>
                  <td style={{ fontWeight: 600 }}>{item.name}</td>
                  <td>
                    <span style={{ textTransform: 'capitalize', color: 'var(--muted)', fontSize: '0.85rem' }}>
                      {item.category}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {item.minimum_stock} {item.unit_of_measure}
                  </td>
                  <td
                    style={{
                      textAlign: 'right',
                      fontWeight: 700,
                      fontVariantNumeric: 'tabular-nums',
                      color: item.current_stock <= 0 ? 'var(--danger)' : item.current_stock <= item.minimum_stock ? 'var(--warn)' : 'var(--ok)',
                    }}
                  >
                    {item.current_stock} {item.unit_of_measure}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    {renderStockBadge(item.current_stock, item.minimum_stock)}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                      <Link
                        href={`/backoffice/inventory/orders/inbound?local_id=${selectedRestaurant}&ingredient_id=${item.id}`}
                        className="secondary-button"
                        style={{
                          padding: '0.3rem 0.65rem',
                          fontSize: '0.78rem',
                          color: '#2dd6a4',
                          borderColor: 'rgba(45, 214, 164, 0.4)',
                          textDecoration: 'none',
                        }}
                      >
                        + Entrada
                      </Link>
                      <Link
                        href={`/backoffice/inventory/orders/outbound?local_id=${selectedRestaurant}&ingredient_id=${item.id}`}
                        className="secondary-button"
                        style={{
                          padding: '0.3rem 0.65rem',
                          fontSize: '0.78rem',
                          color: '#ff8c42',
                          borderColor: 'rgba(255, 140, 66, 0.4)',
                          textDecoration: 'none',
                        }}
                      >
                        - Salida
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
