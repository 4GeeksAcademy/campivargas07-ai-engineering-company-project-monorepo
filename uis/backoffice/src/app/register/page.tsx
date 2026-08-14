'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

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
    maxWidth: '440px',
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
  sectionTitle: {
    color: 'var(--muted)',
    textTransform: 'uppercase' as const,
    fontSize: '0.72rem',
    letterSpacing: '0.1em',
    fontWeight: 700,
    marginBottom: '0.85rem',
  } as React.CSSProperties,
  fieldGroup: {
    display: 'grid',
    gap: '0.85rem',
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
  errorText: {
    color: 'var(--danger)',
    fontSize: '0.78rem',
    marginTop: '0.3rem',
  } as React.CSSProperties,
  divider: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    margin: '1rem 0',
  } as React.CSSProperties,
  dividerLine: {
    flex: 1,
    height: '1px',
    background: 'var(--border)',
  } as React.CSSProperties,
  dividerText: {
    color: 'var(--muted)',
    fontSize: '0.72rem',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
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
  checkIcon: {
    position: 'absolute' as const,
    right: '0.75rem',
    top: '50%',
    transform: 'translateY(-50%)',
    color: 'var(--ok)',
  } as React.CSSProperties,
  submitButton: {
    width: '100%',
    padding: '0.8rem',
    marginTop: '0.5rem',
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
    ...{
      background: 'rgba(255,125,125,0.12)',
      border: '1px solid rgba(255,125,125,0.4)',
      borderRadius: '0.65rem',
      padding: '0.75rem 1rem',
      color: '#ffe1e1',
      fontSize: '0.85rem',
      marginBottom: '1rem',
    },
  } as React.CSSProperties,
  copyright: {
    textAlign: 'center' as const,
    fontSize: '0.72rem',
    color: 'var(--muted)',
    marginTop: '1.25rem',
    opacity: 0.7,
  } as React.CSSProperties,
} as const;

export default function RegisterPage() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    name: '',
    phone: '',
    address: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  const getPasswordStrength = (password: string) => {
    let level = 0;
    if (password.length >= 6) level++;
    if (password.length >= 8) level++;
    if (/[A-Z]/.test(password)) level++;
    if (/[0-9]/.test(password)) level++;
    if (/[^A-Za-z0-9]/.test(password)) level++;

    const labels = ['', 'Débil', 'Regular', 'Buena', 'Fuerte', 'Muy fuerte'];
    const colors = ['', 'var(--danger)', 'var(--warn)', '#e2c541', '#a8d66d', 'var(--ok)'];
    return { level, label: labels[level], color: colors[level] };
  };

  const passwordStrength = getPasswordStrength(formData.password);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    if (!formData.email) newErrors.email = 'El email es requerido';
    else if (!/\S+@\S+\.\S+/.test(formData.email)) newErrors.email = 'El email no es válido';
    if (!formData.password) newErrors.password = 'La contraseña es requerida';
    else if (formData.password.length < 6) newErrors.password = 'Mínimo 6 caracteres';
    if (formData.password !== formData.confirmPassword) newErrors.confirmPassword = 'Las contraseñas no coinciden';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;
    setLoading(true);
    try {
      await register({
        email: formData.email,
        password: formData.password,
        name: formData.name || undefined,
        phone: formData.phone || undefined,
        address: formData.address || undefined,
      });
      router.push('/');
    } catch (err) {
      setErrors({ general: err instanceof Error ? err.message : 'Error al registrar' });
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const inputStyle = (hasError: boolean) => ({
    ...styles.input,
    ...(hasError ? styles.inputError : {}),
  });

  const isValidEmail = formData.email && /\S+@\S+\.\S+/.test(formData.email);
  const passwordsMatch = formData.confirmPassword && formData.password === formData.confirmPassword;

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
        <h1 style={styles.title}>Crear Cuenta</h1>
        <p style={styles.subtitle}>Completa tus datos para unirte al equipo</p>

        {/* Error Banner */}
        {errors.general && (
          <div style={styles.errorBanner}>{errors.general}</div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Required: Access Data */}
          <div style={styles.sectionTitle}>Datos de acceso *</div>
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
                  value={formData.email}
                  onChange={handleChange}
                  style={inputStyle(!!errors.email)}
                  placeholder="tu@email.com"
                />
                {isValidEmail && <span style={styles.checkIcon}>✓</span>}
              </div>
              {errors.email && <p style={styles.errorText}>{errors.email}</p>}
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
                  required
                  value={formData.password}
                  onChange={handleChange}
                  style={inputStyle(!!errors.password)}
                  placeholder="••••••••"
                />
              </div>
              {errors.password && <p style={styles.errorText}>{errors.password}</p>}
              {formData.password && (
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

            {/* Confirm Password */}
            <div>
              <label style={styles.label} htmlFor="confirmPassword">Confirmar contraseña</label>
              <div style={styles.inputWrapper}>
                <span style={styles.inputIcon}>🔒</span>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  required
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  style={inputStyle(!!errors.confirmPassword || (passwordsMatch ? false : false))}
                  placeholder="••••••••"
                />
                {passwordsMatch && <span style={styles.checkIcon}>✓</span>}
              </div>
              {errors.confirmPassword && <p style={styles.errorText}>{errors.confirmPassword}</p>}
            </div>
          </div>

          {/* Divider */}
          <div style={styles.divider}>
            <div style={styles.dividerLine} />
            <span style={styles.dividerText}>Opcional</span>
            <div style={styles.dividerLine} />
          </div>

          {/* Optional: Personal Data */}
          <div style={styles.sectionTitle}>Datos personales</div>
          <div style={styles.fieldGroup}>
            <div>
              <label style={styles.label} htmlFor="name">Nombre completo</label>
              <input
                id="name"
                name="name"
                type="text"
                value={formData.name}
                onChange={handleChange}
                style={styles.input}
                placeholder="Tu nombre"
              />
            </div>
            <div>
              <label style={styles.label} htmlFor="phone">Teléfono</label>
              <input
                id="phone"
                name="phone"
                type="tel"
                value={formData.phone}
                onChange={handleChange}
                style={styles.input}
                placeholder="+57 300 1234567"
              />
            </div>
            <div>
              <label style={styles.label} htmlFor="address">Dirección</label>
              <input
                id="address"
                name="address"
                type="text"
                value={formData.address}
                onChange={handleChange}
                style={styles.input}
                placeholder="Cra. 37 #8A-29"
              />
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            style={{ ...styles.submitButton, ...(loading ? styles.submitButtonDisabled : {}) }}
          >
            {loading ? 'Creando cuenta...' : 'Crear cuenta →'}
          </button>
        </form>

        {/* Login Link */}
        <p style={styles.footerText}>
          ¿Ya tienes cuenta?{' '}
          <a href="/login" style={styles.footerLink}>Inicia sesión</a>
        </p>

        <p style={styles.copyright}>© 2026 Brasaland Digital</p>
      </div>
    </div>
  );
}
