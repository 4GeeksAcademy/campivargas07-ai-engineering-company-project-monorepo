export interface RfpTicketCreatedEvent {
  ticket_id: string;
  client_name: string;
  location: string;
  service_type: string;
  status: string;
  created_at: string;
  departments_needed: string[];
}

export interface RfpEventSubscriptionOptions {
  onEvent: (event: RfpTicketCreatedEvent, eventId: string) => void;
  onStatus?: (status: 'connecting' | 'connected' | 'reconnecting' | 'error' | 'closed') => void;
  onError?: (error: unknown) => void;
  signal?: AbortSignal;
}

const STORAGE_KEY = 'rfp_last_event_id';

function baseUrl() {
  return typeof window !== 'undefined' ? '/api' : 'http://localhost:8000';
}

function token() {
  return typeof window !== 'undefined' ? localStorage.getItem('brasaland_token') : null;
}

function getLastEventId() {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(STORAGE_KEY) || localStorage.getItem(STORAGE_KEY);
}

function setLastEventId(id: string) {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(STORAGE_KEY, id);
  localStorage.setItem(STORAGE_KEY, id);
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function subscribeRfpTicketEvents(options: RfpEventSubscriptionOptions): () => void {
  const { onEvent, onStatus, onError, signal } = options;
  let aborted = false;
  let controller: AbortController | null = null;

  const handleAbort = () => {
    aborted = true;
    controller?.abort();
  };
  signal?.addEventListener('abort', handleAbort);

  (async () => {
    let attempt = 0;
    while (!aborted) {
      onStatus?.('connecting');
      controller = new AbortController();
      const combined = new AbortController();
      const onSignalAbort = () => combined.abort();
      signal?.addEventListener('abort', onSignalAbort);
      controller.signal.addEventListener('abort', onSignalAbort);

      const t = token();
      const headers: HeadersInit = { Accept: 'text/event-stream' };
      if (t) headers['Authorization'] = `Bearer ${t}`;
      const lastId = getLastEventId();
      if (lastId) headers['Last-Event-ID'] = lastId;

      let connected = false;
      try {
        const res = await fetch(`${baseUrl()}/rfp-requests/events`, {
          method: 'GET',
          headers,
          signal: combined.signal,
        });

        if (!res.ok || !res.body) {
          if (res.status === 401) {
            onStatus?.('error');
            onError?.(new Error('unauthorized'));
            return;
          }
          throw new Error(`SSE failed: ${res.status}`);
        }

        connected = true;
        onStatus?.('connected');
        attempt = 0;

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (!aborted) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // Process complete frames separated by blank line.
          let idx: number;
          while ((idx = buffer.indexOf('\n\n')) !== -1) {
            const frame = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            parseFrame(frame, onEvent);
          }
        }
        // Flush trailing frame if any.
        if (buffer.trim()) {
          parseFrame(buffer, onEvent);
        }
        reader.releaseLock();
      } catch (err) {
        if (aborted) break;
        onError?.(err);
      } finally {
        signal?.removeEventListener('abort', onSignalAbort);
      }

      if (aborted) break;
      if (connected) {
        onStatus?.('reconnecting');
      }
      attempt += 1;
      const delay = Math.min(1000 * 2 ** attempt, 16000) + Math.floor(Math.random() * 500);
      await sleep(delay);
    }
    onStatus?.('closed');
  })();

  return () => {
    handleAbort();
  };
}

function parseFrame(frame: string, onEvent: RfpEventSubscriptionOptions['onEvent']) {
  const lines = frame.split(/\r?\n/);
  let eventName = 'message';
  const dataLines: string[] = [];
  let eventId: string | null = null;

  for (const line of lines) {
    if (!line || line.startsWith(':')) continue; // heartbeat / comment
    const colon = line.indexOf(':');
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '');
    if (field === 'event') eventName = value;
    else if (field === 'data') dataLines.push(value);
    else if (field === 'id') eventId = value;
  }

  if (eventName !== 'rfp_ticket_created') return;
  const raw = dataLines.join('\n');
  if (!raw) return;
  try {
    const parsed = JSON.parse(raw) as RfpTicketCreatedEvent;
    if (eventId) setLastEventId(eventId);
    onEvent(parsed, eventId || '');
  } catch {
    // ignore malformed frames
  }
}