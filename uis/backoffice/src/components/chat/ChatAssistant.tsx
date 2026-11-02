'use client';

import { useEffect, useRef, useState } from 'react';
import { authApi } from '@/lib/auth/api';
import { createChatSession } from '@/lib/chat-api';
import { connectChatSocket } from '@/lib/chat-socket';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  status?: string;
}

export function ChatAssistant() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState('disconnected');
  const [partial, setPartial] = useState('');
  const partialRef = useRef('');
  const [locationId, setLocationId] = useState('COL-01');
  const socketRef = useRef<{ send: (event: string, data: any) => void; disconnect: () => void } | null>(null);
  const activeGenerationRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      socketRef.current?.disconnect();
    };
  }, []);

  const startSession = async () => {
    const session = await createChatSession(locationId);
    setSessionId(session.session_id);
    setMessages([]);
    const token = authApi.getToken();
    if (!token) return;
    const handle = connectChatSocket({
      sessionId: session.session_id,
      token,
      onEvent: (event, data) => {
        if (event === 'session_snapshot') {
          setMessages((data.messages || []).map((m: any) => ({ id: m.message_id, role: m.role, content: m.content, status: m.status })));
        } else if (event === 'user_message') {
          setMessages((prev) => [...prev, { id: data.message_id, role: 'user', content: data.text }]);
        } else if (event === 'token_chunk') {
          activeGenerationRef.current = data.generation_id;
          partialRef.current += data.token || '';
          setPartial(partialRef.current);
        } else if (event === 'generation_completed') {
          const content = partialRef.current || '';
          setMessages((prev) => [...prev, { id: data.message_id, role: 'assistant', content, status: 'complete' }]);
          partialRef.current = '';
          setPartial('');
          activeGenerationRef.current = null;
        } else if (event === 'generation_interrupted') {
          const content = partialRef.current || '';
          setMessages((prev) => [...prev, { id: data.message_id, role: 'assistant', content, status: 'interrupted' }]);
          partialRef.current = '';
          setPartial('');
          activeGenerationRef.current = null;
        }
      },
      onStatus: setStatus,
    });
    socketRef.current = handle;
  };

  const sendMessage = () => {
    if (!input.trim() || !socketRef.current) return;
    const text = input.trim();
    setInput('');
    setPartial('');
    socketRef.current.send('user_message', { text });
  };

  const stop = () => {
    if (activeGenerationRef.current && socketRef.current) {
      socketRef.current.send('interrupt_requested', { generation_id: activeGenerationRef.current, new_input: input.trim() || 'corrige' });
    }
  };

  return (
    <div>
      {!sessionId ? (
        <div>
          <label>Location: <input value={locationId} onChange={(e) => setLocationId(e.target.value)} /></label>
          <button onClick={startSession}>Iniciar chat</button>
        </div>
      ) : (
        <>
          <p>Estado: {status} | Sesión: {sessionId}</p>
          <div style={{ border: '1px solid #ccc', padding: 8, minHeight: 200 }}>
            {messages.map((m) => (
              <div key={m.id}><strong>{m.role}:</strong> {m.content} {m.status === 'interrupted' ? '(interrumpido)' : ''}</div>
            ))}
            {partial && <div><strong>assistant:</strong> {partial}</div>}
          </div>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Mensaje" />
          <button onClick={sendMessage}>Enviar</button>
          <button onClick={stop}>Detener</button>
        </>
      )}
    </div>
  );
}