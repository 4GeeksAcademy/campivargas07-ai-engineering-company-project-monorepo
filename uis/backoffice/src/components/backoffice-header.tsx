import Link from "next/link";

type BackofficeHeaderProps = {
  activeView: "overview" | "incidents" | "inventory";
  badge: string;
};

export function BackofficeHeader({ activeView, badge }: BackofficeHeaderProps) {
  return (
    <header className="bo-header">
      <div className="container bo-header-inner">
        <div className="brand-block">
          <span className="brand-dot" />
          <div>
            <h1>Brasaland Backoffice</h1>
            <p>Operaciones, compras e incidencias · Consola interna</p>
          </div>
        </div>

        <nav className="bo-nav" aria-label="Secciones del backoffice">
          <Link className={activeView === "overview" ? "nav-link nav-link-active" : "nav-link"} href="/backoffice/overview">
            Resumen
          </Link>
          <Link className={activeView === "inventory" ? "nav-link nav-link-active" : "nav-link"} href="/backoffice/inventory/products">
            Inventario
          </Link>
          <Link className={activeView === "incidents" ? "nav-link nav-link-active" : "nav-link"} href="/backoffice/incidents">
            Incidencias
          </Link>
        </nav>

        <span className="status-pill">{badge}</span>
      </div>
    </header>
  );
}