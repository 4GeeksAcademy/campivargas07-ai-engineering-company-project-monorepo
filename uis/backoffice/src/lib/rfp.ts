export interface RfpCreateResponse { ticket_id: string; status: string; }
export interface RfpStatusResponse {
  ticket_id: string; status: string; created_at: string; updated_at: string;
  original_filename: string; error_code: string | null; error_detail: string | null;
  processing_started_at: string | null; processing_completed_at: string | null; retry_count: number;
}

function baseUrl() { return typeof window !== 'undefined' ? '/api' : 'http://localhost:8000'; }
function token() { return typeof window !== 'undefined' ? localStorage.getItem('brasaland_token') : null; }

export async function uploadRfp(file: File): Promise<RfpCreateResponse> {
  const form = new FormData();
  form.append('file', file);
  const headers: HeadersInit = {};
  const t = token();
  if (t) headers['Authorization'] = `Bearer ${t}`;
  const res = await fetch(`${baseUrl()}/rfp-requests`, { method: 'POST', headers, body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ detail: 'Error' }))).detail);
  return res.json();
}

export async function getRfpStatus(ticketId: string): Promise<RfpStatusResponse> {
  const headers: HeadersInit = {};
  const t = token();
  if (t) headers['Authorization'] = `Bearer ${t}`;
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}`, { headers });
  if (!res.ok) throw new Error('Error al consultar estado');
  return res.json();
}
