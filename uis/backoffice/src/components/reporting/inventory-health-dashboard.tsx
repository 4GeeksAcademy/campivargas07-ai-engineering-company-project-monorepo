"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { authApi } from "@/lib/auth";

export interface InventoryHealthPeriod {
  snapshot_date: string;
  data_freshness_timestamp: string | null;
  freshness_lag_seconds: number | null;
}

export interface InventoryHealthSummary {
  total_locations_reported: number;
  total_ingredients_monitored: number;
  critical_stockouts_count: number;
  below_minimum_count: number;
  average_stock_level_ratio: number;
  insufficient_stock_attempts_count: number;
}

export interface InventoryHealthItem {
  local_id: string;
  ingredient_id: string;
  ingredient_sku: string;
  ingredient_name: string;
  category: string;
  unit_of_measure: string;
  current_stock: number;
  minimum_stock: number;
  stock_level_ratio: number | null;
  stock_deficit: number;
  is_stockout: boolean;
  is_below_minimum: boolean;
  inbound_quantity: number;
  outbound_quantity: number;
  insufficient_stock_attempts_count: number;
  source_event_count: number;
  computed_at: string | null;
}

export interface InventoryHealthResponse {
  period: InventoryHealthPeriod;
  summary: InventoryHealthSummary;
  items: InventoryHealthItem[];
  pipeline_run_id: string | null;
}

interface InventoryHealthDashboardProps {
  endpoint?: string;
}

export function getReportingApiUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_REPORTING_API_URL || process.env.NEXT_PUBLIC_INTERNAL_API_URL;
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, "");
  }
  return typeof window !== "undefined" ? "/api" : "http://localhost:8000";
}

export function InventoryHealthDashboard({ endpoint }: InventoryHealthDashboardProps) {
  const [data, setData] = useState<InventoryHealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedLocal, setSelectedLocal] = useState<string>("");
  const [onlyCritical, setOnlyCritical] = useState<boolean>(false);

  const executeFetch = useCallback(async () => {
    const baseUrl = getReportingApiUrl();
    const queryParams = new URLSearchParams();
    if (selectedLocal) {
      queryParams.set("local_id", selectedLocal);
    }
    if (onlyCritical) {
      queryParams.set("only_critical", "true");
    }

    const queryString = queryParams.toString();
    const defaultEndpoint = `${baseUrl}/reporting/inventory-health${queryString ? `?${queryString}` : ""}`;
    const targetUrl = endpoint || defaultEndpoint;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const token = authApi.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(targetUrl, {
      method: "GET",
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error("Sesión no autorizada o expirada. Por favor inicie sesión nuevamente.");
      }
      if (response.status === 503) {
        throw new Error("El servicio de base de datos o reporting no está disponible temporalmente.");
      }
      throw new Error(`Error del servidor al obtener reporte de inventario (${response.status})`);
    }

    return response.json();
  }, [endpoint, selectedLocal, onlyCritical]);

  const handleManualRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const json = await executeFetch();
      setData(json);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error de red al cargar reporte de salud de inventario";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [executeFetch]);

  useEffect(() => {
    let ignore = false;

    executeFetch()
      .then((json) => {
        if (!ignore) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          const message = err instanceof Error ? err.message : "Error de red al cargar reporte de salud de inventario";
          setError(message);
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [executeFetch]);

  // Available locations extracted from items or fallback
  const availableLocations = useMemo(() => {
    if (!data?.items) return ["MED-001", "MIA-001"];
    const locs = Array.from(new Set(data.items.map((i) => i.local_id))).sort();
    return locs.length > 0 ? locs : ["MED-001", "MIA-001"];
  }, [data]);

  const isStale = useMemo(() => {
    if (!data?.period?.freshness_lag_seconds) return false;
    // Over 20 minutes (1200 seconds) is considered stale according to business SLA
    return data.period.freshness_lag_seconds > 1200;
  }, [data]);

  const isEmpty = !data || !data.items || data.items.length === 0;

  return (
    <div className="space-y-6" data-testid="inventory-health-dashboard">
      {/* Header and Context */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-gray-200">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">
            Salud de Inventario — Desempeño de Negocio
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Monitoreo proactivo de abastecimiento, quiebres críticos y balance de kardex para Dirección de Operaciones y Supervisores de Sede.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => handleManualRefresh()}
            disabled={loading}
            className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 shadow-sm transition-colors disabled:opacity-50"
            aria-label="Actualizar datos"
          >
            {loading ? "Actualizando..." : "↻ Actualizar datos"}
          </button>
        </div>
      </div>

      {/* Warning Banner: Data Stale / Delayed */}
      {isStale && data?.period && (
        <div
          className="p-4 bg-amber-50 border-l-4 border-amber-500 rounded-r-lg text-amber-900 shadow-sm"
          role="alert"
          data-testid="stale-warning"
        >
          <div className="flex items-center gap-2 font-semibold">
            <span>⚠️</span>
            <span>Información Desactualizada (Retraso de Sincronización)</span>
          </div>
          <p className="mt-1 text-sm text-amber-800">
            La última ejecución del snapshot analítico fue calculada hace{" "}
            <strong>{Math.round((data.period.freshness_lag_seconds || 0) / 60)} minutos</strong>,
            superando la tolerancia máxima de 20 minutos. Se recomienda verificar la ejecución del pipeline.
          </p>
        </div>
      )}

      {/* Metadata Bar */}
      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-gray-50 p-4 rounded-xl border border-gray-200 text-xs">
          <div>
            <span className="text-gray-500 block">Fecha del Snapshot:</span>
            <span className="font-semibold text-gray-800 text-sm">{data.period.snapshot_date}</span>
          </div>
          <div>
            <span className="text-gray-500 block">Frescura de Datos:</span>
            <span className="font-semibold text-gray-800 text-sm">
              {data.period.data_freshness_timestamp
                ? new Date(data.period.data_freshness_timestamp).toLocaleString("es-CO", { timeZone: "UTC" }) + " UTC"
                : "Sin registro"}
            </span>
          </div>
          <div>
            <span className="text-gray-500 block">Estado de Sincronización:</span>
            <span className="font-semibold text-sm">
              {isStale ? (
                <span className="text-amber-700 font-bold">⚠️ Atrasado (&gt; 20 min)</span>
              ) : (
                <span className="text-green-700 font-medium">✓ Actualizado ({data.period.freshness_lag_seconds ? `${Math.round(data.period.freshness_lag_seconds / 60)} min` : "reciente"})</span>
              )}
            </span>
          </div>
        </div>
      )}

      {/* Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label htmlFor="filter-local" className="text-xs font-semibold text-gray-700 uppercase">
              Local:
            </label>
            <select
              id="filter-local"
              value={selectedLocal}
              onChange={(e) => setSelectedLocal(e.target.value)}
              className="text-sm rounded-lg border border-gray-300 bg-white px-3 py-1.5 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Todos los locales</option>
              {availableLocations.map((loc) => (
                <option key={loc} value={loc}>
                  {loc}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={onlyCritical}
              onChange={(e) => setOnlyCritical(e.target.checked)}
              className="rounded border-gray-300 text-red-600 focus:ring-red-500 h-4 w-4"
            />
            <span className="font-medium text-gray-900">Solo ingredientes críticos (agotados / bajo mínimo)</span>
          </label>
        </div>

        {data?.summary && (
          <div className="text-xs text-gray-500">
            Monitoreando <strong>{data.summary.total_ingredients_monitored}</strong> ingredientes en{" "}
            <strong>{data.summary.total_locations_reported}</strong> locales
          </div>
        )}
      </div>

      {/* Loading State */}
      {loading && (
        <div className="p-12 text-center bg-white border border-gray-200 rounded-xl shadow-sm" data-testid="loading-state">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-3" />
          <p className="text-sm font-medium text-gray-600">Cargando indicadores de salud de inventario...</p>
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-center shadow-sm" data-testid="error-state">
          <p className="text-base font-semibold text-red-800">Error al consultar indicadores de inventario</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
          <button
            onClick={() => handleManualRefresh()}
            className="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg shadow-sm transition-colors"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && isEmpty && (
        <div className="p-12 text-center bg-white border border-gray-200 rounded-xl shadow-sm" data-testid="empty-state">
          <p className="text-base font-semibold text-gray-800">Sin datos de inventario disponibles</p>
          <p className="mt-1 text-sm text-gray-500">
            No se encontraron registros de snapshot para el local o criterios seleccionados. Verifique los filtros o ejecute el pipeline.
          </p>
        </div>
      )}

      {/* Populated Data: 4 KPI Cards + Detail Table */}
      {!loading && !error && data && !isEmpty && (
        <div className="space-y-6" data-testid="populated-content">
          {/* 4 Primary Business KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5" data-testid="kpi-cards">
            {/* KPI 1: METRIC_STOCK_LEVEL_RATIO */}
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-2" data-testid="kpi-stock-ratio">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  METRIC_STOCK_LEVEL_RATIO
                </span>
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                  Ratio Promedio
                </span>
              </div>
              <div className="text-3xl font-extrabold text-gray-900">
                {data.summary.average_stock_level_ratio !== null
                  ? `${data.summary.average_stock_level_ratio.toFixed(2)}x`
                  : "N/A"}
              </div>
              <p className="text-xs text-gray-500">
                Nivel de existencias actuales frente al umbral mínimo de seguridad.
              </p>
            </div>

            {/* KPI 2: METRIC_CRITICAL_STOCKOUTS_COUNT */}
            <div
              className={`p-5 rounded-xl border shadow-sm space-y-2 ${
                data.summary.critical_stockouts_count > 0
                  ? "bg-red-50 border-red-200 text-red-900"
                  : "bg-white border-gray-200 text-gray-900"
              }`}
              data-testid="kpi-critical-stockouts"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  METRIC_CRITICAL_STOCKOUTS_COUNT
                </span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
                  data.summary.critical_stockouts_count > 0
                    ? "bg-red-100 text-red-800 border-red-300"
                    : "bg-green-50 text-green-700 border-green-200"
                }`}>
                  {data.summary.critical_stockouts_count > 0 ? "Crítico" : "Óptimo"}
                </span>
              </div>
              <div className="text-3xl font-extrabold">
                {data.summary.critical_stockouts_count}
              </div>
              <p className="text-xs text-gray-500">
                Ingredientes completamente agotados (saldo actual &le; 0).
              </p>
            </div>

            {/* KPI 3: METRIC_BELOW_MINIMUM_COUNT */}
            <div
              className={`p-5 rounded-xl border shadow-sm space-y-2 ${
                data.summary.below_minimum_count > 0
                  ? "bg-amber-50 border-amber-200 text-amber-900"
                  : "bg-white border-gray-200 text-gray-900"
              }`}
              data-testid="kpi-below-minimum"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  METRIC_BELOW_MINIMUM_COUNT
                </span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
                  data.summary.below_minimum_count > 0
                    ? "bg-amber-100 text-amber-800 border-amber-300"
                    : "bg-green-50 text-green-700 border-green-200"
                }`}>
                  {data.summary.below_minimum_count > 0 ? "Alerta" : "Normal"}
                </span>
              </div>
              <div className="text-3xl font-extrabold">
                {data.summary.below_minimum_count}
              </div>
              <p className="text-xs text-gray-500">
                Ingredientes en riesgo por operar bajo el mínimo de seguridad.
              </p>
            </div>

            {/* KPI 4: METRIC_INSUFFICIENT_STOCK_ATTEMPTS_COUNT */}
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm space-y-2" data-testid="kpi-insufficient-attempts">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                  METRIC_INSUFFICIENT_STOCK_ATTEMPTS_COUNT
                </span>
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                  Salidas Bloqueadas
                </span>
              </div>
              <div className="text-3xl font-extrabold text-gray-900">
                {data.summary.insufficient_stock_attempts_count}
              </div>
              <p className="text-xs text-gray-500">
                Intentos de salida en cocina rechazados por falta de saldo en kardex.
              </p>
            </div>
          </div>

          {/* Items Detail Table */}
          <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">Detalle de Salud de Inventario por Local e Ingrediente</h3>
                <p className="text-xs text-gray-500">
                  Particiones analíticas calculadas a partir del kardex transaccional y la telemetría operativa.
                </p>
              </div>
              <span className="text-xs font-medium text-gray-500">
                Mostrando {data.items.length} registros
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="bg-gray-50 text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200">
                  <tr>
                    <th scope="col" className="px-4 py-3">Local</th>
                    <th scope="col" className="px-4 py-3">Ingrediente</th>
                    <th scope="col" className="px-4 py-3">Categoría</th>
                    <th scope="col" className="px-4 py-3 text-right">Stock Actual</th>
                    <th scope="col" className="px-4 py-3 text-right">Mínimo</th>
                    <th scope="col" className="px-4 py-3 text-right">Ratio</th>
                    <th scope="col" className="px-4 py-3 text-right">Déficit</th>
                    <th scope="col" className="px-4 py-3 text-center">Estado</th>
                    <th scope="col" className="px-4 py-3 text-center">Intentos Sin Stock</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.map((item) => {
                    let statusBadgeClass = "bg-green-50 text-green-700 border-green-200";
                    let statusText = "Saludable";

                    if (item.is_stockout) {
                      statusBadgeClass = "bg-red-50 text-red-700 border-red-300 font-bold";
                      statusText = "Agotado";
                    } else if (item.is_below_minimum) {
                      statusBadgeClass = "bg-amber-50 text-amber-700 border-amber-300 font-semibold";
                      statusText = "Bajo Mínimo";
                    }

                    return (
                      <tr key={`${item.local_id}-${item.ingredient_id}`} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-medium text-gray-900 whitespace-nowrap">
                          {item.local_id}
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-semibold text-gray-900">{item.ingredient_name}</div>
                          <div className="text-xs text-gray-400 font-mono">{item.ingredient_sku}</div>
                        </td>
                        <td className="px-4 py-3 capitalize text-gray-500">
                          {item.category}
                        </td>
                        <td className="px-4 py-3 text-right font-medium text-gray-900 whitespace-nowrap">
                          {item.current_stock.toFixed(2)} {item.unit_of_measure}
                        </td>
                        <td className="px-4 py-3 text-right text-gray-500 whitespace-nowrap">
                          {item.minimum_stock.toFixed(2)} {item.unit_of_measure}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-sm whitespace-nowrap">
                          {item.stock_level_ratio !== null ? (
                            <span className={item.stock_level_ratio < 1.0 ? "text-amber-600 font-bold" : "text-gray-700"}>
                              {item.stock_level_ratio.toFixed(2)}x
                            </span>
                          ) : (
                            <span className="text-gray-400 italic">N/A</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right font-medium whitespace-nowrap">
                          {item.stock_deficit > 0 ? (
                            <span className="text-red-600 font-semibold">
                              -{item.stock_deficit.toFixed(2)} {item.unit_of_measure}
                            </span>
                          ) : (
                            <span className="text-gray-400">0.00</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-center whitespace-nowrap">
                          <span className={`inline-block px-2.5 py-0.5 text-xs rounded-full border ${statusBadgeClass}`}>
                            {statusText}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center whitespace-nowrap">
                          {item.insufficient_stock_attempts_count > 0 ? (
                            <span className="inline-block px-2 py-0.5 text-xs font-bold rounded bg-purple-100 text-purple-800 border border-purple-200">
                              {item.insufficient_stock_attempts_count} bloqueos
                            </span>
                          ) : (
                            <span className="text-gray-400">0</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
