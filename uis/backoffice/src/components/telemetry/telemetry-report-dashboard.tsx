"use client";

import React, { useEffect, useState, useCallback } from "react";
import { authApi } from "@/lib/auth";

export interface EventsPerDayItem {
  date: string;
  event_count: number;
}

export interface ErrorRateByTypeItem {
  event_type: string;
  error_count: number;
  error_rate: number;
}

export interface LoginFailureRateItem {
  date: string;
  successful_logins: number;
  failed_logins: number;
  total_attempts: number;
  login_failure_rate: number;
}

export interface ApiLatencyByRouteItem {
  route_path: string;
  request_count: number;
  average_duration_ms: number;
  p95_duration_ms: number;
}

export interface TelemetryReportData {
  period: {
    from: string;
    to: string;
  };
  metrics: {
    events_per_day: EventsPerDayItem[];
    error_rate_by_type: ErrorRateByTypeItem[];
    login_failure_rate_per_day: LoginFailureRateItem[];
    api_latency_by_route: ApiLatencyByRouteItem[];
  };
}

interface TelemetryReportDashboardProps {
  endpoint?: string;
}

export function getTelemetryApiUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_TELEMETRY_API_URL || process.env.NEXT_PUBLIC_INTERNAL_API_URL;
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, "");
  }
  return typeof window !== "undefined" ? "/api" : "http://localhost:8000";
}

export function TelemetryReportDashboard({ endpoint }: TelemetryReportDashboardProps) {
  const [data, setData] = useState<TelemetryReportData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const executeFetch = useCallback(async () => {
    const baseUrl = getTelemetryApiUrl();
    const targetUrl = endpoint || `${baseUrl}/telemetry/report`;

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
      if (response.status === 503) {
        throw new Error("El servicio de base de datos no está disponible temporalmente.");
      }
      throw new Error(`Error del servidor al obtener reporte (${response.status})`);
    }

    return response.json();
  }, [endpoint]);

  const handleManualRefresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const json = await executeFetch();
      setData(json);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error de red al cargar telemetría";
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
          const message = err instanceof Error ? err.message : "Error de red al cargar telemetría";
          setError(message);
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [executeFetch]);

  const isEmpty =
    data &&
    data.metrics.events_per_day.length === 0 &&
    data.metrics.error_rate_by_type.length === 0 &&
    data.metrics.login_failure_rate_per_day.length === 0 &&
    data.metrics.api_latency_by_route.length === 0;

  const maxDailyEvents =
    data && data.metrics.events_per_day.length > 0
      ? Math.max(...data.metrics.events_per_day.map((d) => d.event_count), 1)
      : 1;

  return (
    <div className="space-y-6">
      {/* Cabecera y controles */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-5 bg-white border border-gray-200 rounded-xl shadow-sm">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Reporte Técnico de Telemetría</h2>
          <p className="text-sm text-gray-500">
            Observabilidad, métricas operacionales y rendimiento analizados vía PostgreSQL + Pandas.
          </p>
          {data && (
            <div className="mt-2 text-xs font-mono text-gray-600 bg-gray-50 px-2 py-1 rounded inline-block border border-gray-200" data-testid="report-period">
              Ventana UTC: <span className="font-semibold text-gray-800">{new Date(data.period.from).toLocaleString()}</span> → <span className="font-semibold text-gray-800">{new Date(data.period.to).toLocaleString()}</span>
            </div>
          )}
        </div>
        <div>
          <button
            onClick={() => handleManualRefresh()}
            disabled={loading}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 transition-colors"
          >
            {loading ? "Actualizando..." : "Actualizar reporte"}
          </button>
        </div>
      </div>

      {/* Estado de Carga */}
      {loading && (
        <div className="p-12 text-center bg-white border border-gray-200 rounded-xl shadow-sm" data-testid="loading-state">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-red-500 border-t-transparent" />
          <p className="mt-3 text-sm font-medium text-gray-600">Cargando reporte de telemetría...</p>
        </div>
      )}

      {/* Estado de Error */}
      {!loading && error && (
        <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-center shadow-sm" data-testid="error-state">
          <p className="text-base font-semibold text-red-800">Error al cargar telemetría</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
          <button
            onClick={() => handleManualRefresh()}
            className="mt-4 inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg shadow-sm transition-colors"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Estado Vacío */}
      {!loading && !error && isEmpty && (
        <div className="p-12 text-center bg-white border border-gray-200 rounded-xl shadow-sm" data-testid="empty-state">
          <p className="text-base font-semibold text-gray-800">Sin datos de telemetría</p>
          <p className="mt-1 text-sm text-gray-500">
            No se registraron eventos en el periodo seleccionado o la base de datos se encuentra vacía.
          </p>
        </div>
      )}

      {/* Métricas pobladas */}
      {!loading && !error && data && !isEmpty && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="metrics-container">
          {/* Métrica 1: Volumen diario de eventos */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h3 className="font-semibold text-gray-900">Volumen Diario de Eventos</h3>
                <p className="text-xs text-gray-500">Total de eventos agregados por fecha UTC (events_per_day)</p>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                {data.metrics.events_per_day.reduce((acc, d) => acc + d.event_count, 0)} eventos
              </span>
            </div>

            {data.metrics.events_per_day.length === 0 ? (
              <p className="text-sm text-gray-400 italic">Sin actividad registrada.</p>
            ) : (
              <div className="space-y-3 pt-2">
                {data.metrics.events_per_day.map((item) => {
                  const pct = Math.round((item.event_count / maxDailyEvents) * 100);
                  return (
                    <div key={item.date} className="space-y-1">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-gray-700">{item.date}</span>
                        <span className="text-gray-900 font-semibold">{item.event_count} eventos</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                        <div
                          className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Métrica 2: Tasa de errores técnicos por tipo */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h3 className="font-semibold text-gray-900">Errores Técnicos por Tipo</h3>
                <p className="text-xs text-gray-500">Proporción de excepciones y fallas (error_rate_by_type)</p>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded bg-red-50 text-red-700 border border-red-200">
                {data.metrics.error_rate_by_type.reduce((acc, e) => acc + e.error_count, 0)} errores
              </span>
            </div>

            {data.metrics.error_rate_by_type.length === 0 ? (
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 font-medium">
                ✓ Cero errores técnicos registrados en el periodo.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead>
                    <tr className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      <th className="pb-2">Tipo de error</th>
                      <th className="pb-2 text-right">Cantidad</th>
                      <th className="pb-2 text-right">Tasa (%)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.metrics.error_rate_by_type.map((err) => (
                      <tr key={err.event_type} className="hover:bg-gray-50">
                        <td className="py-2 font-mono text-xs text-gray-800 font-medium">{err.event_type}</td>
                        <td className="py-2 text-right text-gray-700 font-semibold">{err.error_count}</td>
                        <td className="py-2 text-right">
                          <span className="inline-block px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-800">
                            {err.error_rate.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Métrica 3: Tasa diaria de fallos de login */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h3 className="font-semibold text-gray-900">Fallos de Autenticación Diarios</h3>
                <p className="text-xs text-gray-500">Porcentaje de fallos sobre intentos (login_failure_rate_per_day)</p>
              </div>
            </div>

            {data.metrics.login_failure_rate_per_day.length === 0 ? (
              <p className="text-sm text-gray-400 italic">Sin intentos de inicio de sesión en el periodo.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead>
                    <tr className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      <th className="pb-2">Fecha</th>
                      <th className="pb-2 text-center">Éxitos</th>
                      <th className="pb-2 text-center">Fallos</th>
                      <th className="pb-2 text-center">Total</th>
                      <th className="pb-2 text-right">Tasa Fallo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.metrics.login_failure_rate_per_day.map((login) => (
                      <tr key={login.date} className="hover:bg-gray-50">
                        <td className="py-2 font-medium text-gray-800">{login.date}</td>
                        <td className="py-2 text-center text-green-600 font-semibold">{login.successful_logins}</td>
                        <td className="py-2 text-center text-red-600 font-semibold">{login.failed_logins}</td>
                        <td className="py-2 text-center text-gray-700">{login.total_attempts}</td>
                        <td className="py-2 text-right">
                          <span
                            className={`inline-block px-2 py-0.5 text-xs font-bold rounded ${
                              login.login_failure_rate === 0
                                ? "bg-green-100 text-green-800"
                                : login.login_failure_rate > 30
                                ? "bg-red-100 text-red-800"
                                : "bg-amber-100 text-amber-800"
                            }`}
                          >
                            {login.login_failure_rate.toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Métrica 4: Latencia de API por ruta */}
          <div className="p-5 bg-white border border-gray-200 rounded-xl shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h3 className="font-semibold text-gray-900">Latencia de API por Ruta</h3>
                <p className="text-xs text-gray-500">Muestreo de duración en milisegundos (api_latency_by_route)</p>
              </div>
            </div>

            {data.metrics.api_latency_by_route.length === 0 ? (
              <p className="text-sm text-gray-400 italic">Sin mediciones de latencia registradas.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead>
                    <tr className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      <th className="pb-2">Ruta</th>
                      <th className="pb-2 text-center">Reqs</th>
                      <th className="pb-2 text-right">Promedio (ms)</th>
                      <th className="pb-2 text-right">P95 (ms)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {data.metrics.api_latency_by_route.map((lat) => (
                      <tr key={lat.route_path} className="hover:bg-gray-50">
                        <td className="py-2 font-mono text-xs text-gray-800 font-medium">{lat.route_path}</td>
                        <td className="py-2 text-center text-gray-700">{lat.request_count}</td>
                        <td className="py-2 text-right text-gray-700">{lat.average_duration_ms.toFixed(1)}</td>
                        <td className="py-2 text-right">
                          <span
                            className={`inline-block px-2 py-0.5 text-xs font-bold rounded ${
                              lat.p95_duration_ms > 300
                                ? "bg-red-100 text-red-800"
                                : lat.p95_duration_ms > 150
                                ? "bg-amber-100 text-amber-800"
                                : "bg-green-100 text-green-800"
                            }`}
                          >
                            {lat.p95_duration_ms.toFixed(1)} ms
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
