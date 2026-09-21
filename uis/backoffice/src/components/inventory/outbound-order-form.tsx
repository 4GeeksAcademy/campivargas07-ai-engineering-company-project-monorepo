'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  RESTAURANT_LOCATIONS,
  DEFAULT_RESTAURANT_ID,
  RESTAURANT_STORAGE_KEY,
  getRestaurantLabel,
} from '@/lib/constants/restaurants';
import { inventoryApi, InventoryApiError, type IngredientWithStock, type InventoryOrder } from '@/lib/inventory';

export function OutboundOrderForm() {
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
  const [checkingStock, setCheckingStock] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [successOrder, setSuccessOrder] = useState<InventoryOrder | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [quantityError, setQuantityError] = useState<string | null>(null);
  const [reconciliationWarning, setReconciliationWarning] = useState<string | null>(null);
  const [isReconciling, setIsReconciling] = useState<boolean>(false);

  const fetchProductsIdRef = useRef(0);
  const checkStockIdRef = useRef(0);

  const reconcileStock = async (ingId: string, restId: string) => {
    setIsReconciling(true);
    try {
      const updated = await inventoryApi.getProduct(ingId, restId);
      setCurrentStock(updated.current_stock);
      setIngredients((prev) =>
        prev.map((item) => (item.id === updated.id ? { ...item, current_stock: updated.current_stock } : item))
      );
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
    const currentFetchId = ++fetchProductsIdRef.current;

    inventoryApi
      .listProducts(restaurantId)
      .then((data) => {
        if (isMounted && currentFetchId === fetchProductsIdRef.current) {
          setIngredients(data);
          setLoadingIngredients(false);
          if (data.length > 0) {
            const defaultId = initialIngredientId && data.some((i) => i.id === initialIngredientId)
              ? initialIngredientId
              : data[0].id;
            setIngredientId((prev) => (prev && data.some((i) => i.id === prev) ? prev : defaultId));
          } else {
            setIngredientId('');
          }
        }
      })
      .catch((err) => {
        if (isMounted && currentFetchId === fetchProductsIdRef.current) {
          setErrorMessage(err instanceof Error ? err.message : 'Error al cargar catálogo de ingredientes');
          setLoadingIngredients(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [restaurantId, initialIngredientId]);

  // Reactive stock check when restaurant or ingredient changes
  useEffect(() => {
    if (!ingredientId || !restaurantId) {
      return;
    }

    let isMounted = true;
    const currentStockId = ++checkStockIdRef.current;

    inventoryApi
      .getProduct(ingredientId, restaurantId)
      .then((item) => {
        if (isMounted && currentStockId === checkStockIdRef.current) {
          setCurrentStock(item.current_stock);
          setCheckingStock(false);
        }
      })
      .catch(() => {
        if (isMounted && currentStockId === checkStockIdRef.current) {
          setCheckingStock(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [ingredientId, restaurantId]);

  const handleRestaurantChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newId = e.target.value;
    setRestaurantId(newId);
    setLoadingIngredients(true);
    setCheckingStock(true);
    setCurrentStock(null);
    localStorage.setItem(RESTAURANT_STORAGE_KEY, newId);
    setSuccessOrder(null);
    setErrorMessage(null);
    setQuantityError(null);
  };

  const handleIngredientChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newIngId = e.target.value;
    setIngredientId(newIngId);
    setCheckingStock(true);
    setCurrentStock(null);
    setSuccessOrder(null);
    setErrorMessage(null);
    setQuantityError(null);
  };

  const selectedIngredient = ingredients.find((i) => i.id === ingredientId);
  const parsedQty = parseFloat(quantity);
  const isValidQty = !isNaN(parsedQty) && parsedQty > 0;
  const isOverStock = currentStock !== null && isValidQty && parsedQty > currentStock;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setQuantityError(null);
    setSuccessOrder(null);

    if (isNaN(parsedQty) || parsedQty <= 0) {
      setQuantityError('La cantidad debe ser un número estrictamente mayor a 0');
      return;
    }

    if (currentStock !== null && parsedQty > currentStock) {
      setQuantityError(`Stock insuficiente: disponible ${currentStock} ${selectedIngredient?.unit_of_measure || ''}`);
      return;
    }

    if (!ingredientId) {
      setErrorMessage('Por favor seleccione un ingrediente del catálogo');
      return;
    }

    setSubmitting(true);
    try {
      const order = await inventoryApi.createOutboundOrder({
        ingredient_id: ingredientId,
        local_id: restaurantId,
        quantity: parsedQty,
      });

      setSuccessOrder(order);
      setQuantity('');
      setReconciliationWarning(null);

      // Immediately decrement stock in memory without requiring manual reload (optimistic update)
      const baseStock = currentStock !== null ? currentStock : (selectedIngredient?.current_stock ?? 0);
      const newStock = Math.max(0, baseStock - order.quantity);
      setCurrentStock(newStock);
      setIngredients((prev) =>
        prev.map((item) =>
          item.id === order.ingredient_id ? { ...item, current_stock: newStock } : item
        )
      );

      // Reconcile with authoritative backend stock
      await reconcileStock(order.ingredient_id, order.local_id);
    } catch (err) {
      // Retain entered values so user can adjust amount
      if (err instanceof InventoryApiError && err.status === 400) {
        setQuantityError(err.detail);
      } else {
        setErrorMessage(err instanceof Error ? err.message : 'Error al registrar orden de salida');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: '640px', margin: '0 auto', display: 'grid', gap: '1.25rem' }}>
      <div>
        <h2 style={{ fontSize: '1.35rem', marginBottom: '0.25rem' }}>Registrar Salida de Stock (Outbound)</h2>
        <p style={{ color: 'var(--muted)', fontSize: '0.86rem' }}>
          Consumo operativo, mermas o despacho de cocina en sede
        </p>
      </div>

      {successOrder && (
        <div className="feedback feedback-ok" role="alert" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <strong>✓ Salida registrada exitosamente:</strong> Se retiraron{' '}
            <strong>
              {successOrder.quantity} {selectedIngredient?.unit_of_measure || ''}
            </strong>{' '}
            de <strong>{successOrder.ingredient_name}</strong> en la sede{' '}
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

      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '1.1rem' }}>
        <div>
          <label htmlFor="outbound-restaurant" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.35rem' }}>
            Restaurante origen:
          </label>
          <select
            id="outbound-restaurant"
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
          <label htmlFor="outbound-ingredient" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.35rem' }}>
            Ingrediente:
          </label>
          {loadingIngredients ? (
            <div style={{ color: 'var(--muted)', fontSize: '0.85rem', padding: '0.5rem 0' }}>
              Cargando ingredientes...
            </div>
          ) : (
            <select
              id="outbound-ingredient"
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
              {ingredients.length === 0 && <option value="">No hay ingredientes registrados</option>}
              {ingredients.map((ing) => (
                <option key={ing.id} value={ing.id}>
                  {ing.name} (SKU: {ing.sku}) — {ing.unit_of_measure}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Reactive Stock Balance Card */}
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
            <strong
              style={{
                fontSize: '1rem',
                color: checkingStock ? 'var(--muted)' : (currentStock ?? 0) <= 0 ? 'var(--danger)' : 'var(--ok)',
              }}
            >
              {checkingStock ? 'Consultando...' : `${currentStock ?? 0} ${selectedIngredient.unit_of_measure}`}
            </strong>
          </div>
        )}

        {/* Client-side Overstock Warning */}
        {isOverStock && (
          <div
            className="feedback feedback-error"
            role="status"
            style={{
              background: 'rgba(255, 189, 89, 0.12)',
              borderColor: 'rgba(255, 189, 89, 0.4)',
              color: '#ffeacc',
            }}
          >
            ⚠️ <strong>Advertencia de sobregiro:</strong> La cantidad solicitada ({parsedQty}) supera el stock disponible ({currentStock}{' '}
            {selectedIngredient?.unit_of_measure}). El envío ha sido deshabilitado preventivamente para evitar un error transaccional.
          </div>
        )}

        <div>
          <label htmlFor="outbound-quantity" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.35rem' }}>
            Cantidad a retirar {selectedIngredient ? `(${selectedIngredient.unit_of_measure})` : ''}:
          </label>
          <input
            id="outbound-quantity"
            type="number"
            step="0.01"
            min="0.01"
            required
            value={quantity}
            onChange={(e) => {
              setQuantity(e.target.value);
              setErrorMessage(null);
              setQuantityError(null);
            }}
            placeholder="Ej: 10.0"
            disabled={submitting}
            style={{
              width: '100%',
              padding: '0.65rem 0.85rem',
              borderRadius: '0.5rem',
              background: '#07111f',
              border: isOverStock || quantityError ? '1px solid var(--danger, #ff5c77)' : '1px solid var(--border)',
              color: 'var(--fg)',
              fontSize: '0.9rem',
              outline: 'none',
            }}
          />
          {quantityError && (
            <div
              role="alert"
              style={{
                color: 'var(--danger, #ff5c77)',
                fontSize: '0.83rem',
                marginTop: '0.35rem',
                fontWeight: 500,
              }}
            >
              ❌ {quantityError}
            </div>
          )}
        </div>

        <button
          type="submit"
          className="primary-button"
          disabled={submitting || loadingIngredients || checkingStock || isOverStock || !isValidQty || ingredients.length === 0}
          style={{
            marginTop: '0.5rem',
            padding: '0.8rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
          }}
        >
          {submitting ? 'Validando y procesando salida...' : 'Registrar Salida de Stock'}
        </button>
      </form>
    </div>
  );
}
