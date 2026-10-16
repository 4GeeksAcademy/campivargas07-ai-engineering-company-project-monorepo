import { authApi } from '@/lib/auth/api';

export async function askKnowledge(question: string, signal?: AbortSignal): Promise<string> {
  const token = authApi.getToken();
  if (!token) throw new Error('Inicia sesión para consultar los manuales.');
  const response = await fetch('/api/knowledge/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question }),
    signal,
  });
  if (response.status === 401) {
    authApi.logout();
    throw new Error('Tu sesión venció. Inicia sesión de nuevo.');
  }
  if (!response.ok) throw new Error('No pudimos consultar los manuales. Inténtalo de nuevo.');
  const result: unknown = await response.json().catch(() => null);
  if (!result || typeof result !== 'object' || !('answer' in result) ||
      typeof result.answer !== 'string' || !result.answer.trim()) {
    throw new Error('No recibimos una respuesta válida. Inténtalo de nuevo.');
  }
  return result.answer;
}
