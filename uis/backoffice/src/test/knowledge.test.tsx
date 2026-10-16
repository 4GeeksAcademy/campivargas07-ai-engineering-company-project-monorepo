import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { KnowledgeAssistant } from '@/components/knowledge/KnowledgeAssistant';
import { askKnowledge } from '@/lib/knowledge-api';
import { authApi } from '@/lib/auth/api';

vi.mock('@/lib/knowledge-api', () => ({ askKnowledge: vi.fn() }));

beforeEach(() => vi.clearAllMocks());

describe('KnowledgeAssistant', () => {
  it('blocks empty input and renders loading then the answer as text', async () => {
    let finish!: (answer: string) => void;
    vi.mocked(askKnowledge).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    render(<KnowledgeAssistant />);
    expect(screen.getByRole('button', { name: 'Consultar' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Tu pregunta'), { target: { value: '¿Puntos?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(screen.getByRole('status')).toHaveTextContent('Consultando');
    expect(screen.getByRole('button')).toBeDisabled();
    await act(async () => finish('<script>texto</script>'));
    expect(screen.getByRole('region', { name: 'Respuesta' })).toHaveTextContent('<script>texto</script>');
    expect(document.querySelector('script')).toBeNull();
  });

  it('preserves the question and retries after an error', async () => {
    vi.mocked(askKnowledge).mockRejectedValueOnce(new Error('private details')).mockResolvedValueOnce('Respuesta');
    render(<KnowledgeAssistant />);
    fireEvent.change(screen.getByLabelText('Tu pregunta'), { target: { value: 'consulta' } });
    fireEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByRole('alert')).not.toHaveTextContent('private');
    expect(screen.getByLabelText('Tu pregunta')).toHaveValue('consulta');
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await waitFor(() => expect(screen.getByRole('region', { name: 'Respuesta' })).toBeInTheDocument());
    expect(askKnowledge).toHaveBeenCalledTimes(2);
  });

  it('aborts outstanding work on unmount', () => {
    vi.mocked(askKnowledge).mockReturnValue(new Promise(() => {}));
    const { unmount } = render(<KnowledgeAssistant />);
    fireEvent.change(screen.getByLabelText('Tu pregunta'), { target: { value: 'q' } });
    fireEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    const signal = vi.mocked(askKnowledge).mock.calls[0][1];
    unmount();
    expect(signal?.aborted).toBe(true);
  });
});

// Test the real client in this suite while the component remains independently mocked.
describe('knowledge HTTP client', () => {
  it('uses the existing token and same-origin proxy', async () => {
    const real = await vi.importActual<typeof import('@/lib/knowledge-api')>('@/lib/knowledge-api');
    vi.spyOn(authApi, 'getToken').mockReturnValue('test-token');
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ answer: 'ok' })));
    const controller = new AbortController();
    expect(await real.askKnowledge('q', controller.signal)).toBe('ok');
    expect(fetchMock).toHaveBeenCalledWith('/api/knowledge/query', expect.objectContaining({
      method: 'POST', signal: controller.signal,
      headers: expect.objectContaining({ Authorization: 'Bearer test-token' }), body: JSON.stringify({ question: 'q' }),
    }));
    vi.restoreAllMocks();
  });

  it('does not send a request without a session', async () => {
    const real = await vi.importActual<typeof import('@/lib/knowledge-api')>('@/lib/knowledge-api');
    vi.spyOn(authApi, 'getToken').mockReturnValue(null);
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    await expect(real.askKnowledge('q')).rejects.toThrow(/Inicia sesión/);
    expect(fetchMock).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it.each([null, {}, { answer: '' }, { answer: '  ' }, { answer: 3 }, { answer: ['chunk'] }])(
    'rejects invalid answer contracts (%j)', async (body) => {
      const real = await vi.importActual<typeof import('@/lib/knowledge-api')>('@/lib/knowledge-api');
      vi.spyOn(authApi, 'getToken').mockReturnValue('test-token');
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(body)));
      await expect(real.askKnowledge('q')).rejects.toThrow(/respuesta válida/);
      vi.restoreAllMocks();
    },
  );

  it.each([502, 503, 200])('sanitizes errors and malformed responses (%s)', async (status) => {
    const real = await vi.importActual<typeof import('@/lib/knowledge-api')>('@/lib/knowledge-api');
    vi.spyOn(authApi, 'getToken').mockReturnValue('test-token');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('private provider error', { status }));
    await expect(real.askKnowledge('q')).rejects.toThrow(/Inténtalo de nuevo/);
    vi.restoreAllMocks();
  });

  it('logs out on expired authentication', async () => {
    const real = await vi.importActual<typeof import('@/lib/knowledge-api')>('@/lib/knowledge-api');
    vi.spyOn(authApi, 'getToken').mockReturnValue('expired');
    const logout = vi.spyOn(authApi, 'logout').mockImplementation(() => {});
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 401 }));
    await expect(real.askKnowledge('q')).rejects.toThrow(/sesión venció/);
    expect(logout).toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});
