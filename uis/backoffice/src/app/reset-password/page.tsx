'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { authApi } from '@/lib/auth/api';

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const missingToken = !token;
  const tokenError = missingToken ? 'No se proporcionó un token válido' : '';

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    if (!password) newErrors.password = 'La contraseña es requerida';
    else if (password.length < 6) newErrors.password = 'Mínimo 6 caracteres';
    else if (!/[A-Z]/.test(password)) newErrors.password = 'Debe contener al menos una mayúscula';
    else if (!/[0-9]/.test(password)) newErrors.password = 'Debe contener al menos un dígito';
    if (password !== confirmPassword) newErrors.confirmPassword = 'Las contraseñas no coinciden';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !validateForm()) return;

    setLoading(true);
    setError('');

    try {
      await authApi.resetPassword({ token, new_password: password });
      setSuccess(true);
      setTimeout(() => router.push('/login'), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al restablecer contraseña');
    } finally {
      setLoading(false);
    }
  };

  const getPasswordStrength = (pwd: string) => {
    let level = 0;
    if (pwd.length >= 6) level++;
    if (pwd.length >= 8) level++;
    if (/[A-Z]/.test(pwd)) level++;
    if (/[0-9]/.test(pwd)) level++;
    if (/[^A-Za-z0-9]/.test(pwd)) level++;
    const labels = ['', 'Débil', 'Regular', 'Buena', 'Fuerte', 'Muy fuerte'];
    const colors = ['', 'var(--danger)', 'var(--warn)', '#e2c541', '#a8d66d', 'var(--ok)'];
    return { level, label: labels[level], color: colors[level] };
  };

  const passwordStrength = getPasswordStrength(password);

  if (success) {
    return (
      <div style={styles.page}>
        <div style={styles.card}>
          <h1 style={styles.title}>¡Contraseña actualizada!</h1>
          <p style={styles.subtitle}>Redirigiendo al login...</p>
          <div style={styles.successBanner}>
            Tu contraseña ha sido cambiada exitosamente.
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

        <h1 style={styles.title}>Restablecer contraseña</h1>
        <p style={styles.subtitle}>Ingresa tu nueva contraseña.</p>

        {(error || tokenError) && <div style={styles.errorBanner}>{error || tokenError}</div>}

        {token && (
          <form onSubmit={handleSubmit}>
            <div style={styles.fieldGroup}>
              <div>
                <label style={styles.label} htmlFor="password">Nueva contraseña</label>
                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  style={{...styles.input, ...(errors.password ? styles.inputError : {})}}
                  placeholder="••••••••"
                />
                {errors.password && <p style={styles.errorText}>{errors.password}</p>}
                {password && (
                  <>
                    <div style={styles.strengthLabel}>
                      <span style={{ color: 'var(--muted)' }}>Fortaleza:</span>
                      <span style={{ color: passwordStrength.color }}>{passwordStrength.label}</span>
                    </div>
                    <div style={styles.strengthBar}>
                      <div style={{ ...styles.strengthFill, width: `${(passwordStrength.level / 5) * 100}%`, background: passwordStrength.color }} />
                    </div>
                  </>
                )}
              </div>
              <div>
                <label style={styles.label} htmlFor="confirmPassword">Confirmar contraseña</label>
                <input
                  id="confirmPassword"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  style={{...styles.input, ...(errors.confirmPassword ? styles.inputError : {})}}
                  placeholder="••••••••"
                />
                {errors.confirmPassword && <p style={styles.errorText}>{errors.confirmPassword}</p>}
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !token || !password || !confirmPassword}
              style={{...styles.submitButton, ...(loading ? styles.submitButtonDisabled : {})}}
            >
              {loading ? 'Restableciendo...' : 'Restablecer contraseña'}
            </button>
          </form>
        )}

        <div style={styles.footerText}>
          <Link href="/forgot-password" style={styles.footerLink}>Solicitar nuevo enlace</Link>
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Cargando...</div>}>
      <ResetPasswordForm />
    </Suspense>
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
  inputError: {
    borderColor: 'var(--danger)',
    boxShadow: '0 0 0 2px rgba(255,125,125,0.2)',
  } as React.CSSProperties,
  errorText: {
    color: 'var(--danger)',
    fontSize: '0.78rem',
    marginTop: '0.3rem',
  } as React.CSSProperties,
  strengthBar: {
    height: '4px',
    borderRadius: '2px',
    background: 'rgba(255,255,255,0.08)',
    marginTop: '0.4rem',
    overflow: 'hidden' as const,
  } as React.CSSProperties,
  strengthFill: {
    height: '100%',
    borderRadius: '2px',
    transition: 'width 0.3s ease, background 0.3s ease',
  } as React.CSSProperties,
  strengthLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '0.72rem',
    marginTop: '0.25rem',
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
