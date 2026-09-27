import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Hide the Next.js DevTools "N" indicator (next dev only; never shipped in
  // production builds). The DevTools panel is still reachable via the URL bar.
  devIndicators: false,

  /**
   * Proxy all backend API calls through Next.js so the browser never
   * needs to reach 127.0.0.1:8000 directly.
   *
   * Browser → /_api/auth/login → rewritten to → http://127.0.0.1:8000/auth/login
   * Browser → /_api/api/client/dashboard → rewritten to → http://127.0.0.1:8000/api/client/dashboard
   *
   * Does NOT interfere with the Next.js route at /api/client/telegram/callback
   * because that path is not under /_api/.
   */
  async rewrites() {
    const backend = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/_api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
