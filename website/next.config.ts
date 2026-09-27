import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Hide the Next.js DevTools "N" indicator (next dev only; never shipped in
  // production builds). The DevTools panel is still reachable via the URL bar.
  devIndicators: false,
};

export default nextConfig;
