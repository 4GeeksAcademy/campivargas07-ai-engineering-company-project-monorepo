import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { inventoryApi, InventoryApiError } from "@/lib/inventory";
import { authApi } from "@/lib/auth";

describe("InventoryApiClient", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("includes Authorization: Bearer token when stored in authApi", async () => {
    authApi.setToken("fake-jwt-token");

    const mockProducts = [
      {
        id: "ing-1",
        sku: "ING-001",
        name: "Carne de Res (kg)",
        category: "carne",
        unit_of_measure: "kg",
        minimum_stock: 20,
        perishable: true,
        created_at: "2026-09-12T00:00:00Z",
        local_id: "MED-001",
        current_stock: 8,
      },
    ];

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(mockProducts),
      json: async () => mockProducts,
    });
    global.fetch = fetchMock;

    const result = await inventoryApi.listProducts("MED-001");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [calledUrl, calledOptions] = fetchMock.mock.calls[0];
    expect(calledUrl).toContain("/inventory/products?local_id=MED-001");
    expect(calledOptions.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer fake-jwt-token",
    });
    expect(result).toEqual(mockProducts);
  });

  it("throws InventoryApiError with status 422 if local_id is missing on listProducts", async () => {
    await expect(inventoryApi.listProducts("")).rejects.toThrowError(
      "El identificador de local (local_id) es obligatorio"
    );
  });

  it("creates an inbound order with correct JSON payload", async () => {
    authApi.setToken("test-token");

    const mockResponse = {
      id: "ord-1",
      type: "inbound",
      ingredient_id: "ing-1",
      ingredient_sku: "ING-001",
      ingredient_name: "Carne de Res (kg)",
      local_id: "MED-001",
      quantity: 15,
      user_uuid: "user-123",
      created_at: "2026-09-12T00:00:00Z",
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify(mockResponse),
      json: async () => mockResponse,
    });
    global.fetch = fetchMock;

    const res = await inventoryApi.createInboundOrder({
      ingredient_id: "ing-1",
      local_id: "MED-001",
      quantity: 15,
    });

    const [calledUrl, calledOptions] = fetchMock.mock.calls[0];
    expect(calledUrl).toContain("/inventory/orders/inbound");
    expect(calledOptions.method).toBe("POST");
    expect(JSON.parse(calledOptions.body as string)).toEqual({
      ingredient_id: "ing-1",
      local_id: "MED-001",
      quantity: 15,
    });
    expect(res).toEqual(mockResponse);
  });

  it("creates an outbound order with correct JSON payload", async () => {
    authApi.setToken("test-token");

    const mockResponse = {
      id: "ord-2",
      type: "outbound",
      ingredient_id: "ing-1",
      ingredient_sku: "ING-001",
      ingredient_name: "Carne de Res (kg)",
      local_id: "MED-001",
      quantity: 5,
      user_uuid: "user-123",
      created_at: "2026-09-12T00:00:00Z",
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      text: async () => JSON.stringify(mockResponse),
      json: async () => mockResponse,
    });
    global.fetch = fetchMock;

    const res = await inventoryApi.createOutboundOrder({
      ingredient_id: "ing-1",
      local_id: "MED-001",
      quantity: 5,
    });

    const [calledUrl, calledOptions] = fetchMock.mock.calls[0];
    expect(calledUrl).toContain("/inventory/orders/outbound");
    expect(calledOptions.method).toBe("POST");
    expect(JSON.parse(calledOptions.body as string)).toEqual({
      ingredient_id: "ing-1",
      local_id: "MED-001",
      quantity: 5,
    });
    expect(res).toEqual(mockResponse);
  });

  it("handles HTTP 400 InsufficientStockError cleanly by extracting detail", async () => {
    const errorDetail =
      "Insufficient stock for ingredient 'Carne de Res (kg)' (SKU: ING-001) in restaurant 'MED-001'. Available: 8.0, requested: 100.0";

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: async () => JSON.stringify({ detail: errorDetail }),
      json: async () => ({ detail: errorDetail }),
    });

    await expect(
      inventoryApi.createOutboundOrder({
        ingredient_id: "ing-1",
        local_id: "MED-001",
        quantity: 100,
      })
    ).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(InventoryApiError);
      const apiErr = err as InventoryApiError;
      expect(apiErr.status).toBe(400);
      expect(apiErr.detail).toBe(errorDetail);
      return true;
    });
  });

  it("handles non-JSON error responses gracefully without throwing SyntaxError", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      text: async () => "502 Bad Gateway: Proxy Server Error",
    });

    await expect(inventoryApi.listProducts("MED-001")).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(InventoryApiError);
      const apiErr = err as InventoryApiError;
      expect(apiErr.status).toBe(502);
      expect(apiErr.detail).toContain("502 Bad Gateway");
      return true;
    });
  });

  it("handles HTTP 401 Unauthorized by logging out user", async () => {
    authApi.setToken("expired-token");

    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      text: async () => JSON.stringify({ detail: "Could not validate credentials" }),
      json: async () => ({ detail: "Could not validate credentials" }),
    });

    await expect(inventoryApi.listProducts("MED-001")).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(InventoryApiError);
      expect((err as InventoryApiError).status).toBe(401);
      return true;
    });

    expect(authApi.getToken()).toBeNull();
  });

  it("handles HTTP 422 validation errors with array of items", async () => {
    const errorBody = {
      detail: [
        { loc: ["body", "quantity"], msg: "Input should be greater than 0", type: "greater_than" },
      ],
    };
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: async () => JSON.stringify(errorBody),
      json: async () => errorBody,
    });

    await expect(
      inventoryApi.createInboundOrder({
        ingredient_id: "ing-1",
        local_id: "MED-001",
        quantity: 1,
      })
    ).rejects.toSatisfy((err: unknown) => {
      expect(err).toBeInstanceOf(InventoryApiError);
      expect((err as InventoryApiError).detail).toContain("quantity: Input should be greater than 0");
      return true;
    });
  });

  it("fetches single product and lists orders with query params", async () => {
    const mockProduct = {
      id: "ing-1",
      sku: "ING-001",
      name: "Carne",
      category: "carne",
      unit_of_measure: "kg",
      minimum_stock: 10,
      perishable: true,
      created_at: "2026-09-12T00:00:00Z",
      local_id: "MED-001",
      current_stock: 25,
    };

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(mockProduct),
      json: async () => mockProduct,
    });
    global.fetch = fetchMock;

    const prod = await inventoryApi.getProduct("ing-1", "MED-001");
    expect(prod).toEqual(mockProduct);
    expect(fetchMock.mock.calls[0][0]).toContain("/inventory/products/ing-1?local_id=MED-001");

    // Orders with filters
    const mockOrders = {
      orders: [],
      total: 0,
    };
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(mockOrders),
      json: async () => mockOrders,
    });

    const ordersRes = await inventoryApi.listOrders({
      local_id: "MED-001",
      type: "outbound",
    });
    expect(ordersRes).toEqual(mockOrders);
    expect(fetchMock.mock.calls[1][0]).toContain("/inventory/orders?local_id=MED-001&type=outbound");
  });

  describe("URL resolution and precedence", () => {
    const originalEnv = process.env.NEXT_PUBLIC_INVENTORY_API_URL;

    afterEach(() => {
      process.env.NEXT_PUBLIC_INVENTORY_API_URL = originalEnv;
    });

    it("respects NEXT_PUBLIC_INVENTORY_API_URL when set and strips trailing slashes to prevent double slashes", () => {
      process.env.NEXT_PUBLIC_INVENTORY_API_URL = "http://localhost:8000/";
      expect(inventoryApi.getBaseUrl()).toBe("http://localhost:8000");
      expect(inventoryApi.buildUrl("/inventory/products")).toBe("http://localhost:8000/inventory/products");
      expect(inventoryApi.buildUrl("inventory/products")).toBe("http://localhost:8000/inventory/products");
    });

    it("falls back to /api in browser environment when NEXT_PUBLIC_INVENTORY_API_URL is empty or undefined", () => {
      delete process.env.NEXT_PUBLIC_INVENTORY_API_URL;
      // In JSDOM vitest, window is defined
      expect(inventoryApi.getBaseUrl()).toBe("/api");
      expect(inventoryApi.buildUrl("/inventory/products")).toBe("/api/inventory/products");
      expect(inventoryApi.buildUrl("inventory/products")).toBe("/api/inventory/products");
    });
  });
});
