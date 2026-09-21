import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authApi } from "@/lib/auth";
import { createSupplier, listSuppliers } from "@/lib/suppliers-api";

describe("supplier API client", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("uses the Next.js proxy and returns the supplier list", async () => {
    const payload = { suppliers: [], total: 0 };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => payload,
    });
    global.fetch = fetchMock;

    await expect(listSuppliers("Colombia", "carne")).resolves.toEqual(payload);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/api/suppliers?country=Colombia&category=carne",
    );
  });

  it("sends the bearer token on protected writes", async () => {
    authApi.setToken("supplier-token");
    const supplier = {
      id: "1",
      nombre: "Carnes Premium",
      pais: "Colombia",
      contactoNombre: "Ana",
      contactoEmail: "ana@example.com",
      contactoTelefono: "+57 300 000 0000",
      categoriasQueProvee: ["carne"],
      tiempoEntregaDias: 2,
      montoMinimoOrden: 100,
      moneda: "COP",
      status: "activo" as const,
      updated_at: null,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => supplier,
    });
    global.fetch = fetchMock;

    await createSupplier({
      nombre: supplier.nombre,
      pais: supplier.pais,
      contactoNombre: supplier.contactoNombre,
      contactoEmail: supplier.contactoEmail,
      contactoTelefono: supplier.contactoTelefono,
      categoriasQueProvee: supplier.categoriasQueProvee,
      tiempoEntregaDias: supplier.tiempoEntregaDias,
      montoMinimoOrden: supplier.montoMinimoOrden,
      moneda: supplier.moneda,
      status: supplier.status,
    });

    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer supplier-token",
      },
    });
  });
});
