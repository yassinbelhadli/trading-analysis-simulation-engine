import type { MetadataRoute } from "next";

// Production deployments should set NEXT_PUBLIC_SITE_URL to the canonical
// public origin. The localhost default only applies to local development.
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3010";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = [
    "",
    "/features",
    "/pricing",
    "/faq",
    "/docs",
    "/contact",
    "/terms",
    "/privacy",
    "/risk-disclosure",
  ];
  return routes.map((route) => ({
    url: `${siteUrl}${route}`,
    lastModified: new Date(),
    changeFrequency: route === "" ? "weekly" : "monthly",
    priority: route === "" ? 1 : 0.8,
  }));
}
