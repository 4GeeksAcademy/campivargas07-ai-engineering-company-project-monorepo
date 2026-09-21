'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, user, loading: authLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && user) {
      router.replace('/backoffice/overview');
    }
  }, [authLoading, router, user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      router.push('/backoffice/overview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem', background: 'var(--bg, #0b1118)' }}>
      <div style={{ width: '100%', maxWidth: '420px', background: 'var(--card-bg, #111a24)', border: '1px solid var(--border, #202e3d)', borderRadius: '1rem', padding: '2rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--fg, #f0f4f8)', marginBottom: '0.25rem' }}>Brasaland Backoffice</h1>
          <p style={{ color: 'var(--muted, #8ea0b4)', fontSize: '0.9rem' }}>Consola Interna de Operaciones</p>
        </div>

        {error && (
          <div role="alert" style={{ background: 'rgba(255, 99, 99, 0.15)', border: '1px solid #ff6363', borderRadius: '0.5rem', padding: '0.75rem 1rem', color: '#ffc1c1', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label htmlFor="email" style={{ display: 'block', color: 'var(--muted, #8ea0b4)', fontSize: '0.85rem', marginBottom: '0.35rem', fontWeight: 600 }}>
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@brasaland.com"
              style={{ width: '100%', padding: '0.65rem 0.75rem', background: '#0b1118', border: '1px solid var(--border, #202e3d)', borderRadius: '0.5rem', color: '#f0f4f8', fontSize: '0.9rem' }}
            />
          </div>

          <div>
            <label htmlFor="password" style={{ display: 'block', color: 'var(--muted, #8ea0b4)', fontSize: '0.85rem', marginBottom: '0.35rem', fontWeight: 600 }}>
              Contraseña
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{ width: '100%', padding: '0.65rem 0.75rem', background: '#0b1118', border: '1px solid var(--border, #202e3d)', borderRadius: '0.5rem', color: '#f0f4f8', fontSize: '0.9rem' }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{ width: '100%', marginTop: '0.5rem', padding: '0.75rem', background: 'linear-gradient(135deg, #ff7a18, #af002d)', color: '#fff', border: 'none', borderRadius: '0.5rem', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}
          >
            {loading ? 'Iniciando sesión...' : 'Entrar a la consola'}
          </button>
        </form>

        <p style={{ color: 'var(--muted, #8ea0b4)', fontSize: '0.85rem', marginTop: '1.25rem', textAlign: 'center' }}>
          ¿Necesitas una cuenta? <Link href="/register" style={{ color: '#7bd6ff', fontWeight: 700 }}>Regístrate</Link>
        </p>
      </div>
    </div>
  );
}
