'use client';

import Link from "next/link";
import { useAuth } from "@/lib/auth";

type BackofficeHeaderProps = {
  activeView?: "overview" | "incidents" | "profile";
  badge?: string;
};

export function BackofficeHeader({ activeView = "overview", badge }: BackofficeHeaderProps) {
  const { user, loading, logout } = useAuth();

  return (
    <header className="bo-header">
      <div className="container bo-header-inner">
        <Link href="/" className="brand-block" style={{ textDecoration: 'none' }}>
          <span className="brand-dot" />
          <div>
            <h1>Brasaland Backoffice</h1>
            <p>Operaciones, compras e incidencias · Consola interna</p>
          </div>
        </Link>

        <nav className="bo-nav" aria-label="Secciones del backoffice">
          <Link className={activeView === "overview" ? "nav-link nav-link-active" : "nav-link"} href="/">
            Resumen
          </Link>
          <Link className={activeView === "incidents" ? "nav-link nav-link-active" : "nav-link"} href="/incidents">
            Incidencias
          </Link>
        </nav>

        <div className="auth-header-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          {badge && <span className="status-pill">{badge}</span>}

          {!loading && (
            <>
              {user ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <Link
                    href="/account/profile"
                    className={activeView === "profile" ? "nav-link nav-link-active" : "nav-link"}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}
                    title={`Conectado como ${user.email}`}
                  >
                    <span>👤</span>
                    <span style={{ fontWeight: 600 }}>{user.profile?.name || user.email}</span>
                    <span
                      style={{
                        fontSize: '0.68rem',
                        padding: '0.15rem 0.4rem',
                        borderRadius: '999px',
                        background: 'rgba(74, 140, 255, 0.2)',
                        color: '#7bd6ff',
                        textTransform: 'uppercase',
                        fontWeight: 700,
                      }}
                    >
                      {user.role}
                    </span>
                  </Link>
                  <button
                    onClick={logout}
                    className="secondary-button"
                    style={{
                      padding: '0.4rem 0.8rem',
                      fontSize: '0.8rem',
                      borderRadius: '999px',
                      cursor: 'pointer',
                    }}
                    title="Cerrar sesión"
                  >
                    Salir
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Link
                    href="/login"
                    className="secondary-button link-button"
                    style={{
                      padding: '0.42rem 0.9rem',
                      fontSize: '0.82rem',
                      borderRadius: '999px',
                    }}
                  >
                    Iniciar Sesión
                  </Link>
                  <Link
                    href="/register"
                    className="primary-button link-button"
                    style={{
                      padding: '0.42rem 0.9rem',
                      fontSize: '0.82rem',
                      borderRadius: '999px',
                    }}
                  >
                    Registrarse
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </header>
  );
}