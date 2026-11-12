'use client';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { AuthGuard } from '@/components/auth-guard';
import { BackofficeHeader } from '@/components/backoffice-header';
import { getRfpApprovals, submitDecision, getFinalDocument, startRfpApproval } from '@/lib/rfp-approval';

export default function RfpApprovalPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="rfp-approval" badge="Revisión de propuestas" />
        <main className="container bo-main">
          <Suspense fallback={<p>Cargando aprobación…</p>}>
            <RfpApproval />
          </Suspense>
        </main>
      </div>
    </AuthGuard>
  );
}

function RfpApproval() {
  const searchParams = useSearchParams();
  const [ticketId, setTicketId] = useState(searchParams.get('ticket') ?? '');
  const [summary, setSummary] = useState<any>(null);
  const [finalDoc, setFinalDoc] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [departmentId, setDepartmentId] = useState('marketing');
  const [decision, setDecision] = useState('approve');
  const [comment, setComment] = useState('');
  const [version, setVersion] = useState(1);

  async function load() {
    setError(null);
    try {
      setSummary(await getRfpApprovals(ticketId));
    } catch (e: any) {
      setError(e?.message || 'Error');
    }
  }

  async function start() {
    setError(null);
    try {
      await startRfpApproval(ticketId);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Error');
    }
  }

  async function submit() {
    setError(null);
    try {
      await submitDecision(ticketId, departmentId, decision, comment, version);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Error');
    }
  }

  async function loadFinal() {
    setError(null);
    try {
      setFinalDoc(await getFinalDocument(ticketId));
    } catch (e: any) {
      setError(e?.message || 'Error');
    }
  }

  return (
    <section>
      <h1>Aprobación de RFP</h1>
      <label>
        ID del ticket
        <input value={ticketId} onChange={(e) => {
          setTicketId(e.target.value);
          setSummary(null);
          setFinalDoc(null);
        }} />
      </label>
      <button onClick={start} disabled={!ticketId.trim()}>Iniciar aprobación</button>
      <button onClick={load} disabled={!ticketId.trim()}>Consultar</button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {summary && (
        <div>
          <p>Estado: {summary.status}</p>
          <p>Ciclo de corrección: {summary.correction_cycle}</p>
          <p>Requiere CEO: {String(summary.requires_ceo_approval)}</p>
          {summary.conflicts?.length > 0 && (
            <div>
              <h3>Conflictos</h3>
              {summary.conflicts.map((c: any, i: number) => (
                <p key={i}>{c.trigger_id} - {c.status} - {c.summary}</p>
              ))}
            </div>
          )}
          <div>
            <h3>Decisión</h3>
            <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
              <option value="marketing">marketing</option>
              <option value="operaciones">operaciones</option>
              <option value="procurement">procurement</option>
              <option value="training">training</option>
              <option value="ceo">ceo</option>
            </select>
            <select value={decision} onChange={(e) => setDecision(e.target.value)}>
              <option value="approve">approve</option>
              <option value="reject">reject</option>
              <option value="request_changes">request_changes</option>
            </select>
            <input type="number" value={version} onChange={(e) => setVersion(Number(e.target.value))} />
            <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Comentario" />
            <button onClick={submit}>Enviar decisión</button>
          </div>
          <button onClick={loadFinal}>Ver documento final</button>
        </div>
      )}
      {finalDoc && <pre>{finalDoc.content}</pre>}
    </section>
  );
}