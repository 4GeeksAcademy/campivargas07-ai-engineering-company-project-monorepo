import { describe, it, expect, afterEach, vi } from "vitest";

describe("Next.js Config Rewrites (INTERNAL_API_URL)", () => {
  const originalEnv = process.env.INTERNAL_API_URL;

  afterEach(() => {
    if (originalEnv === undefined) {
      delete process.env.INTERNAL_API_URL;
    } else {
      process.env.INTERNAL_API_URL = originalEnv;
    }
    vi.resetModules();
  });

  it("resolves default fallback to http://127.0.0.1:8000 when INTERNAL_API_URL is unset", async () => {
    delete process.env.INTERNAL_API_URL;
    vi.resetModules();
    const configModule = await import("../../next.config");
    const nextConfig = configModule.default;

    expect(nextConfig.rewrites).toBeDefined();
    if (typeof nextConfig.rewrites === "function") {
      const rewrites = await nextConfig.rewrites();
      const apiRewrite = Array.isArray(rewrites)
        ? rewrites.find((r) => r.source === "/api/:path*")
        : null;
      expect(apiRewrite).toBeDefined();
      expect(apiRewrite?.destination).toBe("http://127.0.0.1:8000/:path*");
    }
  });

  it("resolves to Docker internal service when INTERNAL_API_URL=http://backend:8000", async () => {
    process.env.INTERNAL_API_URL = "http://backend:8000";
    vi.resetModules();
    const configModule = await import("../../next.config");
    const nextConfig = configModule.default;

    if (typeof nextConfig.rewrites === "function") {
      const rewrites = await nextConfig.rewrites();
      const apiRewrite = Array.isArray(rewrites)
        ? rewrites.find((r) => r.source === "/api/:path*")
        : null;
      expect(apiRewrite).toBeDefined();
      expect(apiRewrite?.destination).toBe("http://backend:8000/:path*");
    }
  });

  it("strips trailing slashes from INTERNAL_API_URL to prevent double slashes", async () => {
    process.env.INTERNAL_API_URL = "http://backend:8000/";
    vi.resetModules();
    const configModule = await import("../../next.config");
    const nextConfig = configModule.default;

    if (typeof nextConfig.rewrites === "function") {
      const rewrites = await nextConfig.rewrites();
      const apiRewrite = Array.isArray(rewrites)
        ? rewrites.find((r) => r.source === "/api/:path*")
        : null;
      expect(apiRewrite).toBeDefined();
      expect(apiRewrite?.destination).toBe("http://backend:8000/:path*");
    }
  });
});

