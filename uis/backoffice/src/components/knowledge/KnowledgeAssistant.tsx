"use client";

import { FormEvent, useState } from "react";
import { askKnowledge } from "@/lib/knowledge-api";
import styles from "./KnowledgeAssistant.module.css";

export function KnowledgeAssistant() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim();
    if (!normalized || loading) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const result = await askKnowledge(normalized);
      setAnswer(result.answer);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo completar la consulta.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={styles.layout} aria-labelledby="knowledge-title">
      <div className={styles.intro}>
        <p className="eyebrow">Asistente interno</p>
        <h2 id="knowledge-title">Base de conocimiento Brasaland</h2>
        <p>Consulta los manuales oficiales de lealtad, desperdicio, alérgenos y pedidos a proveedores.</p>
      </div>
      <div className={styles.panel}>
        <form className={styles.form} onSubmit={submit}>
          <label htmlFor="knowledge-question">¿Qué necesitas saber?</label>
          <textarea
            id="knowledge-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ej.: ¿Qué debo comunicar sobre las Costillas BBQ si un cliente reporta alergia al maní?"
            maxLength={2000}
            required
            disabled={loading}
          />
          <p className={styles.hint}>La respuesta se limita a la información disponible en los manuales oficiales.</p>
          <button type="submit" disabled={loading || !question.trim()}>
            {loading ? "Consultando…" : "Consultar"}
          </button>
        </form>
      </div>
      {loading && <p className={styles.status} role="status" aria-live="polite">Buscando en los manuales y preparando una respuesta…</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {answer && <article className={styles.answer} aria-label="Respuesta del asistente"><h3>Respuesta</h3><p>{answer}</p></article>}
    </section>
  );
}
