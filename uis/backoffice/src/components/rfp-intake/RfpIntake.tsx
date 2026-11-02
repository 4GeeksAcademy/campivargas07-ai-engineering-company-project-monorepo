'use client';
import { useState } from 'react';
import { uploadRfp, getRfpStatus, RfpStatusResponse } from '@/lib/rfp';

export function RfpIntake() {
  const [file, setFile] = useState<File | null>(null);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [status, setStatus] = useState<RfpStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleUpload() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const created = await uploadRfp(file);
      setTicketId(created.ticket_id);
      const poll = async () => {
        const s = await getRfpStatus(created.ticket_id);
        setStatus(s);
        if (s.status === 'analizando') setTimeout(poll, 2000);
      };
      poll();
    } catch (e: any) {
      setError(e?.message || 'Error al subir');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h1>Recepcion de RFP</h1>
      <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <button onClick={handleUpload} disabled={!file || loading}>{loading ? 'Subiendo...' : 'Subir PDF'}</button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {ticketId && <p>Ticket: {ticketId}</p>}
      {status && (
        <div>
          <p>Estado: {status.status}</p>
          {status.error_code && <p>Error tecnico: {status.error_code} - {status.error_detail}</p>}
          {status.processing_completed_at && <p>Completado: {status.processing_completed_at}</p>}
        </div>
      )}
    </section>
  );
}
