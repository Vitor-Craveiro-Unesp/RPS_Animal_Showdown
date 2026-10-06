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
const configuredRealtimeUrl = validatedUrl(
  "NEXT_PUBLIC_REALTIME_URL",
  process.env.NEXT_PUBLIC_REALTIME_URL,
  "wss:",
);

// The browser opens the realtime socket directly, while all HTTP API calls go
// through the same-origin rewrite below.  Keep the policy explicit instead of
// relying on a broad default that could make a stored capability easier to
// exfiltrate after a future frontend change.
const realtimeConnectSource =
  configuredRealtimeUrl ??
  (isProductionBuild
    ? undefined
    : "ws://localhost:8000 ws://127.0.0.1:8000");
const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "img-src 'self' data:",
  "media-src 'self'",
  "font-src 'self'",
  // Next emits small bootstrap/style blocks for the static app. No unsafe-eval
  // is needed by the production build.
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  `connect-src 'self'${realtimeConnectSource ? ` ${realtimeConnectSource}` : ""}`,
  ...(isProductionBuild ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    // Keep browser requests same-origin. API_INTERNAL_BASE_URL is server-only,
    // while the browser receives no backend credential or private URL.
    if (!apiBase) throw new Error("API_INTERNAL_BASE_URL is required.");
    return [{ source: "/api/:path*", destination: `${apiBase}/:path*` }];
  },
  async headers() {
    // HSTS remains Vercel-managed: this deployment lives on the shared
    // vercel.app domain, so setting includeSubDomains here would be broader
    // than this application owns.
    return [{ source: "/:path*", headers: securityHeaders }];
  }
};

export default nextConfig;
