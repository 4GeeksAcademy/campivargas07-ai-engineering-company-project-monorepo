'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';

// Icons as components
const FlameIcon = ({ className = "w-8 h-8" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 23C16.9706 23 21 18.9706 21 14C21 11.4141 19.8926 9.08236 18.0837 7.33477C18.5479 5.99613 19 4.38141 19 3C16.6734 4.29372 15 6.56519 15 9C15 9.34061 15.0187 9.67571 15.0552 10.0041C14.3875 9.37178 13.5225 9 12.5 9C10.8431 9 9.5 10.3431 9.5 12C9.5 12.2037 9.51993 12.403 9.55786 12.5956C7.98346 12.2143 6.20029 12.7071 5.17854 14.0676C3.89338 15.7826 4.43885 18.2189 6.32467 19.2446C7.4521 19.8614 8.68973 20.1989 9.95348 20.2227C10.6313 22.3071 12.6842 23 14.1473 23H12Z"/>
  </svg>
);

const MailIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
  </svg>
);

const LockIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
);

const AlertIcon = () => (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);

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
  inputWrapper: {
    position: 'relative' as const,
  } as React.CSSProperties,
  inputIcon: {
    position: 'absolute' as const,
    left: '0.75rem',
    top: '50%',
    transform: 'translateY(-50%)',
    color: 'var(--muted)',
    opacity: 0.6,
    fontSize: '0.9rem',
  } as React.CSSProperties,
  input: {
    width: '100%',
    padding: '0.65rem 0.75rem 0.65rem 2.25rem',
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid var(--border)',
    borderRadius: '0.65rem',
    color: 'var(--fg)',
    fontSize: '0.92rem',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
  } as React.CSSProperties,
  inputError: {
    borderColor: 'var(--danger)',
    boxShadow: '0 0 0 2px rgba(255,125,125,0.2)',
  } as React.CSSProperties,
  checkboxRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '1.25rem',
    fontSize: '0.85rem',
  } as React.CSSProperties,
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.45rem',
    color: 'var(--muted)',
    cursor: 'pointer',
  } as React.CSSProperties,
  forgotLink: {
    color: '#4a8cff',
    textDecoration: 'none',
    fontSize: '0.82rem',
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
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
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
  copyright: {
    textAlign: 'center' as const,
    fontSize: '0.72rem',
    color: 'var(--muted)',
    marginTop: '1.25rem',
    opacity: 0.7,
  } as React.CSSProperties,
} as const;

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [remember, setRemember] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        {/* Logo */}
        <div style={styles.logo}>
          <div style={styles.logoIcon}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
              <path d="M12 23C16.97 23 21 18.97 21 14C21 11.41 19.89 9.08 18.08 7.33C18.55 6 19 4.38 19 3C16.67 4.29 15 6.57 15 9C15 9.34 15.02 9.68 15.06 10C14.39 9.37 13.52 9 12.5 9C10.84 9 9.5 10.34 9.5 12C9.5 12.2 9.52 12.4 9.56 12.6C7.98 12.21 6.2 12.71 5.18 14.07C3.89 15.78 4.44 18.22 6.32 19.24C7.45 19.86 8.69 20.2 9.95 20.22C10.63 22.31 12.68 23 14.15 23H12Z"/>
            </svg>
          </div>
          <span style={{ fontWeight: 700, fontSize: '1.15rem' }}>Brasaland</span>
        </div>

        {/* Title */}
        <h1 style={styles.title}>Iniciar Sesión</h1>
        <p style={styles.subtitle}>Accede a tu panel de control</p>

        {/* Error Banner */}
        {error && <div style={styles.errorBanner}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={styles.fieldGroup}>
            {/* Email */}
            <div>
              <label style={styles.label} htmlFor="email">Email</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}>✉</span>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={styles.input}
                  placeholder="tu@email.com"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label style={styles.label} htmlFor="password">Contraseña</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}>🔒</span>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={styles.input}
                  placeholder="••••••••"
                />
              </div>
            </div>
          </div>

          {/* Remember & Forgot */}
          <div style={styles.checkboxRow}>
            <label style={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                style={{ accentColor: '#4a8cff' }}
              />
              Recordarme
            </label>
            <Link href="/forgot-password" style={styles.forgotLink}>¿Olvidaste tu contraseña?</Link>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            style={{ ...styles.submitButton, ...(loading ? styles.submitButtonDisabled : {}) }}
          >
            {loading ? 'Entrando...' : 'Iniciar sesión →'}
          </button>
        </form>

        {/* Register Link */}
        <p style={styles.footerText}>
          ¿No tienes cuenta?{' '}
          <a href="/register" style={styles.footerLink}>Regístrate aquí</a>
        </p>

        <p style={styles.copyright}>© 2026 Brasaland Digital</p>
      </div>
    </div>
  );
}
