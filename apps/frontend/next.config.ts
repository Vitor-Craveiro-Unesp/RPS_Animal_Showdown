import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    // Keep browser requests same-origin.  This avoids making an API base URL
    // (or any credential) part of the client bundle and works in local dev.
    const apiBase = process.env.API_INTERNAL_BASE_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${apiBase}/:path*` }];
  }
};

export default nextConfig;
