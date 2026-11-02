'use client';
import { useEffect, useState } from 'react';
import { uploadRfp, getRfpStatus, startRfpGeneration, getRfpResult, RfpStatusResponse } from '@/lib/rfp';
import { subscribeRfpTicketEvents, RfpTicketCreatedEvent } from '@/lib/rfp-events';

export function RfpIntake() {
  const [file, setFile] = useState<File | null>(null);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [status, setStatus] = useState<RfpStatusResponse | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'reconnecting' | 'error' | 'closed'>('connecting');
  const [incoming, setIncoming] = useState<RfpTicketCreatedEvent[]>([]);

  const processingStatuses = ['analizando', 'generando_borrador', 'en_evaluación'];

  async function handleUpload() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const created = await uploadRfp(file);
      setTicketId(created.ticket_id);
      poll(created.ticket_id);
    } catch (e: any) {
      setError(e?.message || 'Error al subir');
    } finally {
      setLoading(false);
    }
  }

  function poll(id: string) {
    const run = async () => {
      const s = await getRfpStatus(id);
      setStatus(s);
      if (processingStatuses.includes(s.status)) setTimeout(run, 2000);
      if (s.status === 'analisis_completo' || s.status === 'en_evaluación' || s.status === 'needs_human_review') {
        try { setResult(await getRfpResult(id)); } catch {}
      }
    };
    run();
  }

  async function handleGenerate() {
    if (!ticketId) return;
    setLoading(true);
    setError(null);
    try {
      await startRfpGeneration(ticketId);
      poll(ticketId);
    } catch (e: any) {
      setError(e?.message || 'Error al generar');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    const unsubscribe = subscribeRfpTicketEvents({
      signal: controller.signal,
      onStatus: setConnection,
      onEvent: (event) => {
        setIncoming((prev) => {
          if (prev.some((e) => e.ticket_id === event.ticket_id)) return prev;
          return [event, ...prev];
        });
      },
    });
    return () => {
      unsubscribe();
      controller.abort();
    };
  }, []);

  return (
    <section>
      <h1>Recepcion de RFP</h1>
      <p style={{ fontSize: 12, color: '#666' }}>Notificaciones SSE: {connection}</p>
      <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <button onClick={handleUpload} disabled={!file || loading}>{loading ? 'Subiendo...' : 'Subir PDF'}</button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {ticketId && <p>Ticket: {ticketId}</p>}
      {status && (
        <div>
          <p>Estado: {status.status}</p>
          {status.generation_status && <p>Generacion: {status.generation_status} (iteracion {status.current_iteration})</p>}
          {status.all_sections_approved !== null && <p>Todas las secciones aprobadas: {String(status.all_sections_approved)}</p>}
          {status.needs_human_review && <p>Requiere revision humana</p>}
          {status.error_code && <p>Error tecnico: {status.error_code} - {status.error_detail}</p>}
          {status.processing_completed_at && <p>Completado: {status.processing_completed_at}</p>}
          {status.status === 'analisis_completo' && (
            <button onClick={handleGenerate} disabled={loading}>Generar respuestas</button>
          )}
        </div>
      )}
      {result?.drafts?.length > 0 && (
        <div>
          <h2>Borradores</h2>
          {result.drafts.map((d: any) => (
            <div key={d.id} style={{ border: '1px solid #ccc', padding: 8, marginBottom: 8 }}>
              <strong>{d.department_id} (v{d.version})</strong>
              <p>{d.content}</p>
            </div>
          ))}
          <h2>Evaluaciones</h2>
          {result.evaluations?.map((e: any) => (
            <div key={e.id}>
              <strong>{e.department_id}</strong>: {e.overall_pass ? 'APROBADO' : 'FALLIDO'}
              {!e.overall_pass && <p>{e.feedback_for_generator}</p>}
            </div>
          ))}
          {result.generation_handoff?.requires_ceo_approval && (
            <p>Requiere aprobacion adicional de CEO (Mariana Restrepo).</p>
          )}
        </div>
      )}
      {incoming.length > 0 && (
        <div style={{ marginTop: 16, padding: 12, border: '2px solid #2563eb', background: '#eff6ff', borderRadius: 8 }}>
          <h2 style={{ marginTop: 0 }}>Nuevas RFP recibidas</h2>
          {incoming.map((item) => (
            <div key={item.ticket_id} style={{ padding: 8, marginBottom: 8, background: '#fff', borderRadius: 4 }}>
              <strong>{item.client_name || 'RFP sin nombre'}</strong> — {item.location} — {item.service_type}
              <div style={{ fontSize: 12, color: '#555' }}>
                Ticket: {item.ticket_id} · Estado: {item.status} · {item.created_at}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}