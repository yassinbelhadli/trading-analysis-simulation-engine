import type { MetadataRoute } from "next";

// Production deployments should set NEXT_PUBLIC_SITE_URL to the canonical
// public origin. The localhost default only applies to local development.
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3010";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
