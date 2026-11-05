'use client';

import { useEffect, useRef, useState } from 'react';
import { authApi } from '@/lib/auth/api';
import { createChatSession } from '@/lib/chat-api';
import { connectChatSocket } from '@/lib/chat-socket';
import styles from './ChatAssistant.module.css';

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
  const [locationId, setLocationId] = useState('COL-01');
  const [creating, setCreating] = useState(false);
  const socketRef = useRef<{ send: (event: string, data: any) => void; disconnect: () => void } | null>(null);
  const partialRef = useRef('');
  const activeGenerationRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      socketRef.current?.disconnect();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, partial]);

  const startSession = async () => {
    setCreating(true);
    try {
      const session = await createChatSession(locationId);
      setSessionId(session.session_id);
      setMessages([]);
      setPartial('');
      partialRef.current = '';
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
          } else if (event === 'error') {
            setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: 'assistant', content: data.message || 'Error', status: 'interrupted' }]);
          }
        },
        onStatus: setStatus,
      });
      socketRef.current = handle;
    } finally {
      setCreating(false);
    }
  };

  const endSession = () => {
    socketRef.current?.disconnect();
    socketRef.current = null;
    setSessionId(null);
    setMessages([]);
    setPartial('');
    partialRef.current = '';
    setStatus('disconnected');
  };

  const sendMessage = () => {
    if (!input.trim() || !socketRef.current) return;
    const text = input.trim();
    setInput('');
    partialRef.current = '';
    setPartial('');
    socketRef.current.send('user_message', { text });
  };

  const stop = () => {
    if (activeGenerationRef.current && socketRef.current) {
      socketRef.current.send('interrupt_requested', { generation_id: activeGenerationRef.current, new_input: input.trim() || 'corrige la respuesta anterior' });
      if (input.trim()) setInput('');
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!sessionId) {
    return (
      <div className={styles.card}>
        <div className={styles.header}>
          <span className={styles.title}>Chat con el agente de soporte</span>
        </div>
        <p className={styles.meta}>Crea una sesión para comenzar a chatear con el Manager support agent.</p>
        <div className={styles.inputRow}>
          <input className={styles.input} value={locationId} onChange={(e) => setLocationId(e.target.value)} placeholder="Location (COL-01)" />
          <button className={`${styles.btn} ${styles.primary}`} onClick={startSession} disabled={creating}>
            {creating ? 'Creando...' : 'Iniciar chat'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.title}>Sesión {sessionId}</span>
        <span className={styles.status}>{status}</span>
      </div>
      <div className={styles.messages}>
        {messages.length === 0 && !partial && <div className={styles.empty}>Envía un mensaje para comenzar.</div>}
        {messages.map((m) => (
          <div key={m.id} className={`${styles.msg} ${m.role === 'user' ? styles.user : styles.assistant} ${m.status === 'interrupted' ? styles.interrupted : ''}`}>
            <div>{m.content}</div>
            {m.status === 'interrupted' && <div className={styles.meta}>interrumpido</div>}
          </div>
        ))}
        {partial && (
          <div className={`${styles.msg} ${styles.assistant}`}>
            <span>{partial}</span>
            <span className={styles.cursor} />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className={styles.inputRow}>
        <input className={styles.input} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown} placeholder="Escribe un mensaje..." disabled={status !== 'connected'} />
        <button className={`${styles.btn} ${styles.primary}`} onClick={sendMessage} disabled={!input.trim() || status !== 'connected'}>Enviar</button>
        <button className={`${styles.btn} ${styles.danger}`} onClick={stop} disabled={!activeGenerationRef.current}>Detener</button>
        <button className={`${styles.btn} ${styles.secondary}`} onClick={endSession}>Cerrar</button>
      </div>
    </div>
  );
}