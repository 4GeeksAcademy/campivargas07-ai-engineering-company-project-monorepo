'use client';

import { useState } from 'react';
import Link from 'next/link';
import { authApi } from '@/lib/auth/api';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authApi.forgotPassword({ email: email.trim().toLowerCase() });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al enviar solicitud');
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <div style={styles.logo}>
            <div style={styles.logoIcon}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                <path d="M12 23C16.97 23 21 18.97 21 14C21 11.41 19.89 9.08 18.08 7.33C18.55 6 19 4.38 19 3C16.67 4.29 15 6.57 15 9C15 9.34 15.02 9.68 15.06 10C14.39 9.37 13.52 9 12.5 9C10.84 9 9.5 10.34 9.5 12C9.5 12.2 9.52 12.4 9.56 12.6C7.98 12.21 6.2 12.71 5.18 14.07C3.89 15.78 4.44 18.22 6.32 19.24C7.45 19.86 8.69 20.2 9.95 20.22C10.63 22.31 12.68 23 14.15 23H12Z"/>
              </svg>
            </div>
            <span style={{ fontWeight: 700, fontSize: '1.15rem' }}>Brasaland</span>
          </div>
          <h1 style={styles.title}>Email enviado</h1>
          <p style={styles.subtitle}>
            Si el email {email} está registrado, recibirás un enlace para restablecer tu contraseña.
          </p>
          <div style={styles.successBanner}>
            Revisa tu bandeja de entrada y sigue las instrucciones.
          </div>
          <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
            <Link href="/login" style={styles.footerLink}>Volver al login</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <div style={styles.logoIcon}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
              <path d="M12 23C16.97 23 21 18.97 21 14C21 11.41 19.89 9.08 18.08 7.33C18.55 6 19 4.38 19 3C16.67 4.29 15 6.57 15 9C15 9.34 15.02 9.68 15.06 10C14.39 9.37 13.52 9 12.5 9C10.84 9 9.5 10.34 9.5 12C9.5 12.2 9.52 12.4 9.56 12.6C7.98 12.21 6.2 12.71 5.18 14.07C3.89 15.78 4.44 18.22 6.32 19.24C7.45 19.86 8.69 20.2 9.95 20.22C10.63 22.31 12.68 23 14.15 23H12Z"/>
            </svg>
          </div>
          <span style={{ fontWeight: 700, fontSize: '1.15rem' }}>Brasaland</span>
        </div>

        <h1 style={styles.title}>Olvidaste tu contraseña</h1>
        <p style={styles.subtitle}>Ingresa tu email y te enviaremos un enlace para restablecerla.</p>

        {error && <div style={styles.errorBanner}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={styles.fieldGroup}>
            <div>
              <label style={styles.label} htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={styles.input}
                placeholder="tu@email.com"
              />
            </div>
          </div>

          <button
            type="submit"
            style={{...styles.submitButton, ...(loading ? styles.submitButtonDisabled : {})}}
          >
            {loading ? 'Enviando...' : 'Enviar enlace de recuperación'}
          </button>
        </form>

        <div style={styles.footerText}>
          <Link href="/login" style={styles.footerLink}>Volver al login</Link>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2rem 1rem',
  } as React.CSSProperties,
  card: {
    width: '100%',
    maxWidth: '400px',
    background: 'var(--card)',
    border: '1px solid var(--border)',
    borderRadius: '1rem',
    padding: '2rem 1.75rem',
  } as React.CSSProperties,
  logo: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.75rem',
    marginBottom: '1.5rem',
  } as React.CSSProperties,
  logoIcon: {
    width: '42px',
    height: '42px',
    borderRadius: '12px',
    background: 'linear-gradient(135deg, #ff8c42, #ff6b35)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  } as React.CSSProperties,
  title: {
    fontFamily: 'var(--font-jakarta), sans-serif',
    fontSize: '1.75rem',
    fontWeight: 800,
    marginBottom: '0.35rem',
    textAlign: 'center' as const,
  } as React.CSSProperties,
  subtitle: {
    color: 'var(--muted)',
    fontSize: '0.92rem',
    textAlign: 'center' as const,
    marginBottom: '1.75rem',
  } as React.CSSProperties,
  fieldGroup: {
    display: 'grid',
    gap: '0.9rem',
    marginBottom: '1.25rem',
  } as React.CSSProperties,
  label: {
    display: 'block',
    color: 'var(--muted)',
    fontSize: '0.82rem',
    fontWeight: 600,
    marginBottom: '0.35rem',
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '0.65rem 0.75rem',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid var(--border)',
    borderRadius: '0.65rem',
    color: 'var(--fg)',
    fontSize: '0.92rem',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.2s ease',
  } as React.CSSProperties,
  submitButton: {
    width: '100%',
    padding: '0.8rem',
    border: '0',
    borderRadius: '999px',
    background: 'linear-gradient(135deg, #2dd6a4, #4a8cff)',
    color: '#03121f',
    fontFamily: 'inherit',
    fontWeight: 700,
    fontSize: '0.95rem',
    cursor: 'pointer',
    transition: 'transform 0.2s ease, opacity 0.2s ease',
  } as React.CSSProperties,
  submitButtonDisabled: {
    opacity: 0.55,
    cursor: 'not-allowed',
  } as React.CSSProperties,
  footerText: {
    textAlign: 'center' as const,
    fontSize: '0.85rem',
    color: 'var(--muted)',
    marginTop: '1.25rem',
  } as React.CSSProperties,
  footerLink: {
    color: '#4a8cff',
    fontWeight: 600,
    textDecoration: 'none',
  } as React.CSSProperties,
  errorBanner: {
    background: 'rgba(255,125,125,0.12)',
    border: '1px solid rgba(255,125,125,0.4)',
    borderRadius: '0.65rem',
    padding: '0.75rem 1rem',
    color: '#ffe1e1',
    fontSize: '0.85rem',
    marginBottom: '1rem',
  } as React.CSSProperties,
  successBanner: {
    background: 'rgba(45,214,164,0.12)',
    border: '1px solid rgba(45,214,164,0.4)',
    borderRadius: '0.65rem',
    padding: '0.75rem 1rem',
    color: '#a8f0d4',
    fontSize: '0.85rem',
    marginBottom: '1rem',
  } as React.CSSProperties,
};
