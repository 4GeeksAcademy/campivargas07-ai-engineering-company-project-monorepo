"use client";

import { ChangeEvent, useEffect, useState } from "react";
import {
  type Supplier,
  type SupplierCreatePayload,
  listSuppliers,
  createSupplier,
  updateSupplierRate,
  updateSupplierStatus,
} from "@/lib/suppliers-api";

const COUNTRIES = ["Colombia", "USA"];
const CATEGORIES = ["carne", "verdura", "salsa", "bebida", "empaque", "limpieza"];

function formatMoney(amount: number, currency: string) {
  return currency === "COP"
    ? `$${amount.toLocaleString("es-CO")} COP`
    : `$${amount.toLocaleString("en-US")} USD`;
}

export function SuppliersDirectory() {
  // ── state ──
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // filters
  const [filterCountry, setFilterCountry] = useState("");
  const [filterCategory, setFilterCategory] = useState("");

  // create form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<SupplierCreatePayload>({
    nombre: "",
    pais: "Colombia",
    contactoNombre: "",
    contactoEmail: "",
    contactoTelefono: "",
    categoriasQueProvee: [],
    tiempoEntregaDias: 1,
    montoMinimoOrden: 1,
    moneda: "COP",
    status: "activo",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [formBusy, setFormBusy] = useState(false);

  // inline rate edit
  const [editingRateId, setEditingRateId] = useState<string | null>(null);
  const [editingRateValue, setEditingRateValue] = useState("");

  // ── data loading ──
  async function loadSuppliers() {
    try {
      setLoading(true);
      setError(null);
      const data = await listSuppliers(
        filterCountry || undefined,
        filterCategory || undefined
      );
      setSuppliers(data.suppliers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error loading suppliers");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSuppliers();
  }, [filterCountry, filterCategory]);

  // ── create ──
  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormBusy(true);
    setFormError(null);
    try {
      await createSupplier(form);
      setShowForm(false);
      setForm({
        nombre: "",
        pais: "Colombia",
        contactoNombre: "",
        contactoEmail: "",
        contactoTelefono: "",
        categoriasQueProvee: [],
        tiempoEntregaDias: 1,
        montoMinimoOrden: 1,
        moneda: "COP",
        status: "activo",
      });
      await loadSuppliers();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Error creating supplier");
    } finally {
      setFormBusy(false);
    }
  }

  // ── rate update ──
  async function handleRateUpdate(id: string) {
    const value = parseFloat(editingRateValue);
    if (isNaN(value) || value <= 0) {
      setError("Rate must be a positive number");
      return;
    }
    try {
      await updateSupplierRate(id, value);
      setEditingRateId(null);
      await loadSuppliers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error updating rate");
    }
  }

  // ── status toggle ──
  async function handleStatusToggle(id: string, currentStatus: string) {
    const newStatus = currentStatus === "activo" ? "suspendido" : "activo";
    try {
      await updateSupplierStatus(id, newStatus);
      await loadSuppliers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error updating status");
    }
  }

  // ── form field helpers ──
  function onFormChange(field: keyof SupplierCreatePayload, value: unknown) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function toggleCategory(cat: string) {
    setForm((prev) => {
      const current = prev.categoriasQueProvee;
      const updated = current.includes(cat)
        ? current.filter((c) => c !== cat)
        : [...current, cat];
      return { ...prev, categoriasQueProvee: updated };
    });
  }

  // ── render ──
  return (
    <div className="suppliers-layout">
      {/* Hero */}
      <section className="card suppliers-hero">
        <div>
          <p className="eyebrow">Directorio de proveedores</p>
          <h2>Gestiona el catálogo de proveedores de Brasaland</h2>
          <p className="muted">
            Alta, baja, actualización de tarifas y estado de proveedores — una
            única fuente de verdad para compras y operaciones.
          </p>
        </div>
        <div className="hero-metrics">
          <div>
            <span>Total proveedores</span>
            <strong>{suppliers.length}</strong>
          </div>
          <div>
            <span>Activos</span>
            <strong>{suppliers.filter((s) => s.status === "activo").length}</strong>
          </div>
          <div>
            <span>Suspendidos</span>
            <strong>{suppliers.filter((s) => s.status === "suspendido").length}</strong>
          </div>
        </div>
      </section>

      {/* Toolbar */}
      <section className="card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Directorio</p>
            <h3>Listado de proveedores</h3>
          </div>
          <button
            className="primary-button"
            onClick={() => setShowForm(!showForm)}
            type="button"
          >
            {showForm ? "Cancelar" : "+ Nuevo proveedor"}
          </button>
        </div>

        {/* Filters */}
        <div className="filters-row">
          <div className="filter-group">
            <label htmlFor="filter-country">País</label>
            <select
              id="filter-country"
              value={filterCountry}
              onChange={(e) => setFilterCountry(e.target.value)}
            >
              <option value="">Todos</option>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="filter-group">
            <label htmlFor="filter-category">Categoría</label>
            <select
              id="filter-category"
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
            >
              <option value="">Todas</option>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          {(filterCountry || filterCategory) && (
            <button
              className="secondary-button"
              onClick={() => { setFilterCountry(""); setFilterCategory(""); }}
              type="button"
              style={{ padding: "0.5rem 0.9rem", fontSize: "0.82rem" }}
            >
              Limpiar filtros
            </button>
          )}
        </div>

        {/* Create form */}
        {showForm && (
          <form className="create-form" onSubmit={handleCreate}>
            <div className="form-grid">
              <div className="form-field">
                <label htmlFor="f-nombre">Nombre *</label>
                <input id="f-nombre" required value={form.nombre}
                  onChange={(e) => onFormChange("nombre", e.target.value)} />
              </div>
              <div className="form-field">
                <label htmlFor="f-pais">País *</label>
                <select id="f-pais" value={form.pais}
                  onChange={(e) => onFormChange("pais", e.target.value)}>
                  {COUNTRIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div className="form-field">
                <label htmlFor="f-contacto">Contacto *</label>
                <input id="f-contacto" required value={form.contactoNombre}
                  onChange={(e) => onFormChange("contactoNombre", e.target.value)} />
              </div>
              <div className="form-field">
                <label htmlFor="f-email">Email *</label>
                <input id="f-email" type="email" required value={form.contactoEmail}
                  onChange={(e) => onFormChange("contactoEmail", e.target.value)} />
              </div>
              <div className="form-field">
                <label htmlFor="f-tel">Teléfono *</label>
                <input id="f-tel" required value={form.contactoTelefono}
                  onChange={(e) => onFormChange("contactoTelefono", e.target.value)} />
              </div>
              <div className="form-field">
                <label htmlFor="f-dias">Días entrega *</label>
                <input id="f-dias" type="number" min={1} max={30} required
                  value={form.tiempoEntregaDias}
                  onChange={(e) => onFormChange("tiempoEntregaDias", parseInt(e.target.value) || 1)} />
              </div>
              <div className="form-field">
                <label htmlFor="f-tarifa">Tarifa mín. *</label>
                <input id="f-tarifa" type="number" min={0.01} step="0.01" required
                  value={form.montoMinimoOrden}
                  onChange={(e) => onFormChange("montoMinimoOrden", parseFloat(e.target.value) || 0)} />
              </div>
              <div className="form-field">
                <label htmlFor="f-moneda">Moneda *</label>
                <select id="f-moneda" value={form.moneda}
                  onChange={(e) => onFormChange("moneda", e.target.value)}>
                  <option value="COP">COP</option>
                  <option value="USD">USD</option>
                </select>
              </div>
            </div>
            <div className="form-field">
              <label>Categorías *</label>
              <div className="categories-toggle">
                {CATEGORIES.map((cat) => (
                  <button key={cat} type="button"
                    className={form.categoriasQueProvee.includes(cat) ? "cat-btn active" : "cat-btn"}
                    onClick={() => toggleCategory(cat)}>
                    {cat}
                  </button>
                ))}
              </div>
            </div>
            {formError && <p className="feedback feedback-error">{formError}</p>}
            <div className="actions-row">
              <button className="primary-button" type="submit" disabled={formBusy}>
                {formBusy ? "Creando..." : "Crear proveedor"}
              </button>
              <button className="secondary-button" type="button"
                onClick={() => { setShowForm(false); setFormError(null); }}>
                Cancelar
              </button>
            </div>
          </form>
        )}

        {error && <p className="feedback feedback-error">{error}</p>}

        {/* Table */}
        {loading ? (
          <p className="muted" style={{ padding: "1rem 0" }}>Cargando proveedores...</p>
        ) : suppliers.length === 0 ? (
          <p className="muted" style={{ padding: "1rem 0" }}>No hay proveedores para los filtros seleccionados.</p>
        ) : (
          <table className="table suppliers-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>País</th>
                <th>Categorías</th>
                <th>Tarifa</th>
                <th>Estado</th>
                <th>Última actualización</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr key={s.id} className={s.status === "suspendido" ? "row-suspended" : ""}>
                  <td className="cell-name">{s.nombre}</td>
                  <td>{s.pais}</td>
                  <td>
                    <div className="categories-cell">
                      {s.categoriasQueProvee.map((c) => (
                        <span key={c} className="chip chip-ok">{c}</span>
                      ))}
                    </div>
                  </td>
                  <td>
                    {editingRateId === s.id ? (
                      <div className="inline-edit">
                        <input
                          type="number"
                          min={0.01}
                          step="0.01"
                          value={editingRateValue}
                          onChange={(e) => setEditingRateValue(e.target.value)}
                          className="inline-input"
                          onKeyDown={(e) => { if (e.key === "Enter") handleRateUpdate(s.id); }}
                          autoFocus
                        />
                        <button className="primary-button" style={{ padding: "0.3rem 0.6rem", fontSize: "0.78rem" }}
                          onClick={() => handleRateUpdate(s.id)} type="button">
                          OK
                        </button>
                        <button className="secondary-button" style={{ padding: "0.3rem 0.6rem", fontSize: "0.78rem" }}
                          onClick={() => setEditingRateId(null)} type="button">
                          ✕
                        </button>
                      </div>
                    ) : (
                      <span className="rate-value" title="Click to edit"
                        style={{ cursor: "pointer" }}
                        onClick={() => { setEditingRateId(s.id); setEditingRateValue(String(s.montoMinimoOrden)); }}>
                        {formatMoney(s.montoMinimoOrden, s.moneda)}
                      </span>
                    )}
                  </td>
                  <td>
                    <span className={s.status === "activo" ? "chip chip-ok" : "chip chip-danger"}>
                      {s.status}
                    </span>
                  </td>
                  <td className="muted">
                    {s.updated_at
                      ? new Date(s.updated_at).toLocaleString()
                      : "—"}
                  </td>
                  <td>
                    <button
                      className={s.status === "activo" ? "chip chip-danger" : "chip chip-ok"}
                      style={{ cursor: "pointer", border: "none", font: "inherit" }}
                      onClick={() => handleStatusToggle(s.id, s.status)}
                      type="button"
                    >
                      {s.status === "activo" ? "Suspender" : "Activar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
