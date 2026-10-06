import type { NextConfig } from "next";

const isProductionBuild = process.env.NODE_ENV === "production";

function validatedUrl(name: string, value: string | undefined, requiredProtocol: "http:" | "https:" | "ws:" | "wss:") {
  if (!value) {
    if (isProductionBuild) throw new Error(`${name} is required for a production build.`);
    return undefined;
  }
  let parsed: URL;
  try { parsed = new URL(value); } catch { throw new Error(`${name} must be an absolute URL.`); }
  if (isProductionBuild && parsed.protocol !== requiredProtocol) {
    throw new Error(`${name} must use ${requiredProtocol} in a production build.`);
  }
  return parsed.toString().replace(/\/$/, "");
}

const apiBase = validatedUrl(
  "API_INTERNAL_BASE_URL",
  process.env.API_INTERNAL_BASE_URL ?? (isProductionBuild ? undefined : "http://localhost:8000"),
  "https:",
);
// The browser consumes this public WebSocket URL. Validate it during the build
// so production cannot silently fall back to a localhost socket.
validatedUrl("NEXT_PUBLIC_REALTIME_URL", process.env.NEXT_PUBLIC_REALTIME_URL, "wss:");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    // Keep browser requests same-origin. API_INTERNAL_BASE_URL is server-only,
    // while the browser receives no backend credential or private URL.
    if (!apiBase) throw new Error("API_INTERNAL_BASE_URL is required.");
    return [{ source: "/api/:path*", destination: `${apiBase}/:path*` }];
  }
};

export default nextConfig;
