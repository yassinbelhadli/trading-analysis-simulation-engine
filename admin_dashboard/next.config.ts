import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Hide the Next.js DevTools "N" indicator (next dev only; never shipped in
  // production builds). The DevTools panel is still reachable via the URL bar.
  devIndicators: false,
  async redirects() {
    return [
      { source: "/users", destination: "/dashboard/users", permanent: false },
      { source: "/licenses", destination: "/dashboard/licenses", permanent: false },
      { source: "/health", destination: "/dashboard/system", permanent: false },
      { source: "/audit", destination: "/dashboard/audit", permanent: false },
      { source: "/accounts", destination: "/dashboard/accounts", permanent: false },
      { source: "/accounts/:path*", destination: "/dashboard/accounts/:path*", permanent: false },
      { source: "/dashboard/admin", destination: "/dashboard/revenue", permanent: false },
    ];
  },
};

export default nextConfig;
