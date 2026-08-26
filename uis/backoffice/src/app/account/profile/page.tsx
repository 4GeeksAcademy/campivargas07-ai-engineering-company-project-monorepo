'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { authApi } from '@/lib/auth/api';
import { BackofficeHeader } from '@/components/backoffice-header';

export default function ProfilePage() {
  const { user, loading: authLoading, refreshUser } = useAuth();
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    address: '',
  });

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user?.profile) {
      setFormData({
        name: user.profile.name || '',
        phone: user.profile.phone || '',
        address: user.profile.address || '',
      });
    }
  }, [user]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage({ type: '', text: '' });

    try {
      await authApi.updateProfile(formData);
      await refreshUser();
      setEditing(false);
      setMessage({ type: 'success', text: 'Perfil actualizado correctamente' });
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error instanceof Error ? error.message : 'Error al actualizar el perfil' 
      });
    } finally {
      setSaving(false);
    }
  };

  if (authLoading) {
    return (
      <div className="backoffice-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
        <p className="muted">Cargando perfil...</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="backoffice-page">
      <BackofficeHeader activeView="profile" badge="Cuenta de usuario" />

      <main className="container bo-main" style={{ maxWidth: '720px', margin: '0 auto', paddingTop: '2rem' }}>
        <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link href="/" className="nav-link" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.88rem' }}>
            ← Volver al panel
          </Link>
        </div>

        <section className="card" style={{ padding: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>Mi Perfil</h2>
              <p className="muted" style={{ fontSize: '0.85rem' }}>Información de tu cuenta y datos de contacto</p>
            </div>
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="secondary-button"
                style={{ padding: '0.45rem 1rem', fontSize: '0.85rem' }}
              >
                Editar Perfil
              </button>
            )}
          </div>

          {message.text && (
            <div className={message.type === 'success' ? 'feedback feedback-ok' : 'feedback feedback-error'} style={{ marginBottom: '1.25rem' }}>
              {message.text}
            </div>
          )}

          <div style={{ display: 'grid', gap: '1.25rem' }}>
            <div>
              <label style={{ display: 'block', color: 'var(--muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
                Email
              </label>
              <div style={{ fontSize: '1.05rem', fontWeight: 600 }}>{user.email}</div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', color: 'var(--muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
                  Rol de Acceso
                </label>
                <div>
                  <span className="chip chip-ok" style={{ textTransform: 'uppercase' }}>{user.role}</span>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', color: 'var(--muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
                  Estado de Cuenta
                </label>
                <div>
                  <span className={`chip ${user.is_active ? 'chip-ok' : 'chip-danger'}`}>
                    {user.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </div>
              </div>
            </div>

            <div style={{ height: '1px', background: 'var(--border)', margin: '0.5rem 0' }} />

            {editing ? (
              <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '1rem' }}>
                <div>
                  <label htmlFor="name" style={{ display: 'block', color: 'var(--muted)', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                    Nombre completo
                  </label>
                  <input
                    id="name"
                    name="name"
                    type="text"
                    value={formData.name}
                    onChange={handleChange}
                    style={{
                      width: '100%',
                      padding: '0.65rem 0.85rem',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid var(--border)',
                      borderRadius: '0.65rem',
                      color: 'var(--fg)',
                      fontSize: '0.92rem',
                    }}
                    placeholder="Ej. Lucía Fernández"
                  />
                </div>

                <div>
                  <label htmlFor="phone" style={{ display: 'block', color: 'var(--muted)', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                    Teléfono
                  </label>
                  <input
                    id="phone"
                    name="phone"
                    type="tel"
                    value={formData.phone}
                    onChange={handleChange}
                    style={{
                      width: '100%',
                      padding: '0.65rem 0.85rem',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid var(--border)',
                      borderRadius: '0.65rem',
                      color: 'var(--fg)',
                      fontSize: '0.92rem',
                    }}
                    placeholder="+57 300 1234567"
                  />
                </div>

                <div>
                  <label htmlFor="address" style={{ display: 'block', color: 'var(--muted)', fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                    Dirección
                  </label>
                  <input
                    id="address"
                    name="address"
                    type="text"
                    value={formData.address}
                    onChange={handleChange}
                    style={{
                      width: '100%',
                      padding: '0.65rem 0.85rem',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid var(--border)',
                      borderRadius: '0.65rem',
                      color: 'var(--fg)',
                      fontSize: '0.92rem',
                    }}
                    placeholder="Cra. 37 #8A-29, Medellín"
                  />
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                  <button
                    type="submit"
                    disabled={saving}
                    className="primary-button"
                    style={{ padding: '0.6rem 1.25rem', fontSize: '0.9rem' }}
                  >
                    {saving ? 'Guardando...' : 'Guardar Cambios'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false);
                      if (user?.profile) {
                        setFormData({
                          name: user.profile.name || '',
                          phone: user.profile.phone || '',
                          address: user.profile.address || '',
                        });
                      }
                    }}
                    className="secondary-button"
                    style={{ padding: '0.6rem 1.25rem', fontSize: '0.9rem' }}
                  >
                    Cancelar
                  </button>
                </div>
              </form>
            ) : (
              <div style={{ display: 'grid', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', color: 'var(--muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>
                    Nombre completo
                  </label>
                  <div style={{ color: user.profile?.name ? 'var(--fg)' : 'var(--muted)' }}>
                    {user.profile?.name || 'No especificado'}
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', color: 'var(--muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>
                    Teléfono
                  </label>
                  <div style={{ color: user.profile?.phone ? 'var(--fg)' : 'var(--muted)' }}>
                    {user.profile?.phone || 'No especificado'}
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', color: 'var(--muted)', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>
                    Dirección
                  </label>
                  <div style={{ color: user.profile?.address ? 'var(--fg)' : 'var(--muted)' }}>
                    {user.profile?.address || 'No especificada'}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
