'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { askKnowledge } from '@/lib/knowledge-api';
import styles from './KnowledgeAssistant.module.css';

export function KnowledgeAssistant() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setAnswer('');
    setError('');
    try {
      const result = await askKnowledge(question.trim(), controller.signal);
      if (!controller.signal.aborted) setAnswer(result);
    } catch {
      if (!controller.signal.aborted) setError('No pudimos consultar los manuales. Puedes reintentar.');
    } finally {
      if (!controller.signal.aborted) {
        request.current = null;
        setLoading(false);
      }
    }
  }

  return (
    <section className={styles.panel} aria-labelledby="knowledge-title">
      <h2 id="knowledge-title">Consulta los manuales de Brasaland</h2>
      <p>Resuelve dudas sobre Brasa Points, desperdicio, alérgenos y pedidos a proveedores.</p>
      <form onSubmit={submit} aria-busy={loading}>
        <label htmlFor="knowledge-question">Tu pregunta</label>
        <textarea id="knowledge-question" value={question} maxLength={2000} required
          disabled={loading} onChange={(event) => { setQuestion(event.target.value); setError(''); }}
          placeholder="¿Cuándo debo generar un pedido de emergencia?" />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? 'Consultando…' : error ? 'Reintentar' : 'Consultar'}
        </button>
      </form>
      {loading && <p role="status">Consultando los manuales…</p>}
      {error && <p role="alert" className={styles.error}>{error}</p>}
      {answer && <section aria-label="Respuesta" aria-live="polite" className={styles.answer}>
        <h3>Respuesta</h3><p>{answer}</p>
      </section>}
    </section>
  );
}
