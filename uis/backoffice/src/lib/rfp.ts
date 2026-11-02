export interface RfpCreateResponse { ticket_id: string; status: string; }
export interface RfpStatusResponse {
  ticket_id: string; status: string; created_at: string; updated_at: string;
  original_filename: string; error_code: string | null; error_detail: string | null;
  processing_started_at: string | null; processing_completed_at: string | null; retry_count: number;
  generation_status: string | null; current_iteration: number | null;
  all_sections_approved: boolean | null; needs_human_review: boolean | null;
}
export interface RfpSectionDraftResponse {
  id: string; department_id: string; version: number; iteration: number;
  content: string; generator_id: string; model: string; status: string; created_at: string;
}
export interface RfpSectionEvaluationResponse {
  id: string; department_id: string; draft_id: string | null; iteration: number;
  readability: any; relevance: any; compliance: any; overall_pass: boolean;
  feedback_for_generator: string; evaluated_at: string;
}
export interface RfpGenerateResponse { ticket_id: string; status: string; run_id: string; }

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

export async function startRfpGeneration(ticketId: string): Promise<RfpGenerateResponse> {
  const headers: HeadersInit = {};
  const t = token();
  if (t) headers['Authorization'] = `Bearer ${t}`;
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/generate`, { method: 'POST', headers });
  if (!res.ok) throw new Error((await res.json().catch(() => ({ detail: 'Error' }))).detail);
  return res.json();
}

export async function getRfpResult(ticketId: string): Promise<any> {
  const headers: HeadersInit = {};
  const t = token();
  if (t) headers['Authorization'] = `Bearer ${t}`;
  const res = await fetch(`${baseUrl()}/rfp-requests/${ticketId}/result`, { headers });
  if (!res.ok) throw new Error('Error al consultar resultado');
  return res.json();
}