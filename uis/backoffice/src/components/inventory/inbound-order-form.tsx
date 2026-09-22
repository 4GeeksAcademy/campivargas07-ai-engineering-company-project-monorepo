'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  RESTAURANT_LOCATIONS,
  DEFAULT_RESTAURANT_ID,
  RESTAURANT_STORAGE_KEY,
  getRestaurantLabel,
} from '@/lib/constants/restaurants';
import { inventoryApi, type IngredientWithStock, type InventoryOrder } from '@/lib/inventory';
import { telemetryService } from '@/services/telemetry';

export function InboundOrderForm() {
  const searchParams = useSearchParams();
  const initialLocalId = searchParams.get('local_id');
  const initialIngredientId = searchParams.get('ingredient_id');

  const [restaurantId, setRestaurantId] = useState<string>(
    initialLocalId || (typeof window !== 'undefined' ? localStorage.getItem(RESTAURANT_STORAGE_KEY) : null) || DEFAULT_RESTAURANT_ID
  );
  const [ingredientId, setIngredientId] = useState<string>(initialIngredientId || '');
  const [quantity, setQuantity] = useState<string>('');
  const [ingredients, setIngredients] = useState<IngredientWithStock[]>([]);
  const [currentStock, setCurrentStock] = useState<number | null>(null);
  const [loadingIngredients, setLoadingIngredients] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successOrder, setSuccessOrder] = useState<InventoryOrder | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reconciliationWarning, setReconciliationWarning] = useState<string | null>(null);
  const [isReconciling, setIsReconciling] = useState<boolean>(false);

  const fetchIdRef = useRef(0);

  const reconcileStock = async (ingId: string, restId: string) => {
    setIsReconciling(true);
    try {
      const updated = await inventoryApi.getProduct(ingId, restId);
      setIngredients((prev) =>
        prev.map((item) => (item.id === updated.id ? { ...item, current_stock: updated.current_stock } : item))
      );
      setCurrentStock(updated.current_stock);
      setReconciliationWarning(null);
    } catch {
      setReconciliationWarning(
        'La orden se registró exitosamente, pero no pudo recuperarse el balance actualizado desde el servidor.'
      );
    } finally {
      setIsReconciling(false);
    }
  };

  // Load ingredients when restaurant changes
  useEffect(() => {
    let isMounted = true;
    const currentFetchId = ++fetchIdRef.current;

    inventoryApi
      .listProducts(restaurantId)
      .then((data) => {
        if (isMounted && currentFetchId === fetchIdRef.current) {
          setIngredients(data);
          setLoadingIngredients(false);
          if (data.length > 0) {
            setIngredientId((prev) => {
              if (prev && data.some((i) => i.id === prev)) return prev;
              if (initialIngredientId && data.some((i) => i.id === initialIngredientId)) {
                return initialIngredientId;
              }
              return data[0].id;
            });
          } else {
            setIngredientId('');
          }
        }
      })
      .catch((err) => {
        if (isMounted && currentFetchId === fetchIdRef.current) {
          setErrorMessage(err instanceof Error ? err.message : 'Error al cargar catálogo de ingredientes');
          setLoadingIngredients(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [restaurantId, initialIngredientId]);

  const handleRestaurantChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newId = e.target.value;
    setRestaurantId(newId);
    setLoadingIngredients(true);
    localStorage.setItem(RESTAURANT_STORAGE_KEY, newId);
    setSuccessOrder(null);
    setErrorMessage(null);
  };

  const handleIngredientChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setIngredientId(e.target.value);
    setSuccessOrder(null);
    setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessOrder(null);

    const parsedQty = parseFloat(quantity);
    if (isNaN(parsedQty) || parsedQty <= 0) {
      setErrorMessage('La cantidad debe ser un número estrictamente mayor a 0');
      return;
    }

    if (!ingredientId) {
      setErrorMessage('Por favor seleccione un ingrediente del catálogo');
      return;
    }

    setSubmitting(true);
    try {
      const order = await inventoryApi.createInboundOrder({
        ingredient_id: ingredientId,
        local_id: restaurantId,
        quantity: parsedQty,
      });

      setSuccessOrder(order);
      setQuantity('');
      setReconciliationWarning(null);

      // Immediately update dynamic stock in memory for instant feedback
      const baseStock = currentStock !== null ? currentStock : (selectedIngredient?.current_stock ?? 0);
      const newStock = baseStock + order.quantity;
      setCurrentStock(newStock);
      setIngredients((prev) =>
        prev.map((item) =>
          item.id === order.ingredient_id
            ? { ...item, current_stock: newStock }
            : item
        )
      );

      // Track approved business event
      try {
        telemetryService.track('inbound_order_created', {
          order_id: order.id,
          local_id: order.local_id,
          ingredient_id: order.ingredient_id,
          ingredient_sku: order.ingredient_sku,
          quantity: order.quantity,
          unit_of_measure: selectedIngredient?.unit_of_measure || 'kg',
          previous_stock: baseStock,
          resulting_stock: newStock,
        });
      } catch {
        // Telemetry errors must never disrupt user flow
      }

      // Reconcile with authoritative backend stock
      await reconcileStock(order.ingredient_id, order.local_id);
    } catch (err) {
      // Retain entered values on error
      setErrorMessage(err instanceof Error ? err.message : 'Error al registrar la orden de entrada');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedIngredient = ingredients.find((i) => i.id === ingredientId);

  return (
    <div className="card" style={{ maxWidth: '640px', margin: '0 auto', display: 'grid', gap: '1.25rem' }}>
      <div>
        <h2 style={{ fontSize: '1.35rem', marginBottom: '0.25rem' }}>Registrar Entrada de Stock (Inbound)</h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.86rem' }}>
          Recepción de insumos y materias primas en sede operativa
        </p>
      </div>

      {successOrder && (
        <div className="feedback feedback-ok" role="alert" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <strong>✓ Entrada registrada exitosamente:</strong> Se ingresaron{' '}
            <strong>
              {successOrder.quantity} {selectedIngredient?.unit_of_measure || ''}
            </strong>{' '}
            de <strong>{successOrder.ingredient_name}</strong> (SKU: {successOrder.ingredient_sku}) en la sede{' '}
            <strong>{getRestaurantLabel(successOrder.local_id)}</strong>.
          </div>
          <button
            type="button"
            onClick={() => setSuccessOrder(null)}
            aria-label="Cerrar notificación"
            style={{
              background: 'none',
              border: 'none',
              color: 'inherit',
              cursor: 'pointer',
              fontSize: '1rem',
              marginLeft: '0.5rem',
            }}
          >
            ×
          </button>
        </div>
      )}

      {reconciliationWarning && (
        <div
          className="feedback feedback-warning"
          role="alert"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(255, 193, 7, 0.12)',
            border: '1px solid rgba(255, 193, 7, 0.4)',
            color: '#ffc107',
            padding: '0.75rem 1rem',
            borderRadius: '0.5rem',
            fontSize: '0.85rem',
          }}
        >
          <span>⚠️ {reconciliationWarning}</span>
          {successOrder && (
            <button
              type="button"
              onClick={() => reconcileStock(successOrder.ingredient_id, successOrder.local_id)}
              disabled={isReconciling}
              className="secondary-button"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', whiteSpace: 'nowrap', marginLeft: '1rem' }}
            >
              {isReconciling ? 'Sincronizando...' : 'Reintentar sincronización'}
            </button>
          )}
        </div>
      )}

      {errorMessage && (
        <div className="feedback feedback-error" role="alert">
          <strong>Error:</strong> {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate style={{ display: 'grid', gap: '1.1rem' }}>
        <div>
          <label htmlFor="inbound-restaurant" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.35rem' }}>
            Restaurante destino:
          </label>
          <select
            id="inbound-restaurant"
            value={restaurantId}
            onChange={handleRestaurantChange}
            disabled={submitting}
            style={{
              width: '100%',
              padding: '0.65rem 0.85rem',
              borderRadius: '0.5rem',
              background: '#07111f',
              border: '1px solid var(--border)',
              color: 'var(--fg)',
              fontSize: '0.9rem',
              outline: 'none',
            }}
          >
            {RESTAURANT_LOCATIONS.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.nombre} ({loc.id})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="inbound-ingredient" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.35rem' }}>
            Ingrediente:
          </label>
          {loadingIngredients ? (
            <div style={{ color: 'var(--muted)', fontSize: '0.85rem', padding: '0.5rem 0' }}>
              Cargando catálogo de ingredientes...
            </div>
          ) : (
            <select
              id="inbound-ingredient"
              value={ingredientId}
              onChange={handleIngredientChange}
              disabled={submitting || ingredients.length === 0}
              required
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem',
                borderRadius: '0.5rem',
                background: '#07111f',
                border: '1px solid var(--border)',
                color: 'var(--fg)',
                fontSize: '0.9rem',
                outline: 'none',
              }}
            >
              {ingredients.length === 0 && <option value="">No hay ingredientes disponibles</option>}
              {ingredients.map((ing) => (
                <option key={ing.id} value={ing.id}>
                  {ing.name} (SKU: {ing.sku}) — {ing.unit_of_measure}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Current dynamic stock badge */}
        {selectedIngredient && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: '0.65rem',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
              Stock disponible actual en {getRestaurantLabel(restaurantId)}:
            </span>
            {(() => {
              const displayStock = currentStock !== null ? currentStock : (selectedIngredient.current_stock ?? 0);
              return (
                <strong
                  style={{
                    fontSize: '1rem',
                    color: displayStock <= 0 ? 'var(--danger)' : displayStock <= selectedIngredient.minimum_stock ? 'var(--warn)' : 'var(--ok)',
                  }}
                >
                  {displayStock} {selectedIngredient.unit_of_measure}
                </strong>
              );
            })()}
          </div>
        )}

        <div>
          <label htmlFor="inbound-quantity" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.35rem' }}>
            Cantidad a ingresar {selectedIngredient ? `(${selectedIngredient.unit_of_measure})` : ''}:
          </label>
          <input
            id="inbound-quantity"
            type="number"
            step="0.01"
            min="0.01"
            required
            value={quantity}
            onChange={(e) => {
              setQuantity(e.target.value);
              setErrorMessage(null);
            }}
            placeholder="Ej: 25.5"
            disabled={submitting}
            style={{
              width: '100%',
              padding: '0.65rem 0.85rem',
              borderRadius: '0.5rem',
              background: '#07111f',
              border: '1px solid var(--border)',
              color: 'var(--fg)',
              fontSize: '0.9rem',
              outline: 'none',
            }}
          />
        </div>

        <button
          type="submit"
          className="primary-button"
          disabled={submitting || loadingIngredients || ingredients.length === 0}
          style={{
            marginTop: '0.5rem',
            padding: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
          }}
        >
          {submitting ? 'Procesando entrada...' : 'Registrar Entrada de Stock'}
        </button>
      </form>
    </div>
  );
}
