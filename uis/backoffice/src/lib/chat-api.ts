import { authApi } from '@/lib/auth/api';

export interface ChatSessionResponse {
  session_id: string;
  agent_id: string;
  user_id: string;
  location_id: string;
  status: string;
  created_at: string;
}

export async function createChatSession(locationId: string): Promise<ChatSessionResponse> {
  const token = authApi.getToken();
  const response = await fetch('/api/chat/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ location_id: locationId }),
  });
  if (response.status === 401) {
    authApi.logout();
    throw new Error('Tu sesión venció. Inicia sesión de nuevo.');
  }
  if (!response.ok) throw new Error('No se pudo crear la sesión de chat.');
  return response.json();
}