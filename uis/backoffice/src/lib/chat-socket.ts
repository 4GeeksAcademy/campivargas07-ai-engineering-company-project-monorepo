export interface ChatSocketOptions {
  sessionId: string;
  token: string;
  onEvent: (event: string, data: any) => void;
  onStatus?: (status: 'connecting' | 'connected' | 'reconnecting' | 'closed' | 'error') => void;
}

export function connectChatSocket(options: ChatSocketOptions): { send: (event: string, data: any) => void; disconnect: () => void } {
  const { sessionId, token, onEvent, onStatus } = options;
  let socket: WebSocket | null = null;
  let closed = false;
  let attempt = 0;

  const connect = () => {
    onStatus?.('connecting');
    const url = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/chat/ws?session_id=${encodeURIComponent(sessionId)}&token=${encodeURIComponent(token)}`;
    socket = new WebSocket(url);
    socket.onopen = () => {
      attempt = 0;
      onStatus?.('connected');
    };
    socket.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data);
        onEvent(parsed.event, parsed.data);
      } catch {
        // ignore malformed
      }
    };
    socket.onerror = () => onStatus?.('error');
    socket.onclose = () => {
      if (closed) {
        onStatus?.('closed');
        return;
      }
      onStatus?.('reconnecting');
      attempt += 1;
      const delay = Math.min(1000 * 2 ** attempt, 16000) + Math.floor(Math.random() * 500);
      setTimeout(connect, delay);
    };
  };

  connect();
  return {
    send: (event: string, data: any) => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ event, data }));
      }
    },
    disconnect: () => {
      closed = true;
      socket?.close();
    },
  };
}