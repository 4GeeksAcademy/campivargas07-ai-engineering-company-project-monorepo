export interface RfpApprovalSummary {
  ticket_id: string;
  status: string;
  approvals: any[];
  conflicts: any[];
  requires_ceo_approval: boolean;
  ceo_approved: boolean;
  correction_cycle: number;
  final_document_id: string | null;
  final_document_reference: string | null;
}

function baseUrl() { return typeof window !== 'undefined' ? '/api' : 'http://localhost:8000'; }
function token() { return typeof window !== 'undefined' ? localStorage.getItem('brasaland_token') : null; }
function headers() {
  const h: HeadersInit = {};
  const t = token();
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

export async function startRfpApproval(ticketId: string) {
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/approval/start`, { method: 'POST', headers: headers() });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ detail: 'Error' }))).detail);
  return res.json();
}

export async function getRfpApprovals(ticketId: string): Promise<RfpApprovalSummary> {
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/approvals`, { headers: headers() });
  if (!res.ok) throw new Error('Error al consultar aprobaciones');
  return res.json();
}

export async function getDepartmentReview(ticketId: string, departmentId: string) {
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/approvals/${departmentId}`, { headers: headers() });
  if (!res.ok) throw new Error('Error al consultar revisión');
  return res.json();
}

export async function submitDecision(ticketId: string, departmentId: string, decision: string, comment: string, version?: number) {
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/approvals/${departmentId}`, {
    method: 'POST',
    headers: { ...headers(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, comment, version }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ detail: 'Error' }))).detail);
  return res.json();
}

export async function submitCeoDecision(ticketId: string, decision: string, comment: string) {
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/approvals/ceo`, {
    method: 'POST',
    headers: { ...headers(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, comment }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ detail: 'Error' }))).detail);
  return res.json();
}

export async function getFinalDocument(ticketId: string) {
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/final-document`, { headers: headers() });
  if (!res.ok) throw new Error('Error al consultar documento final');
  return res.json();
}