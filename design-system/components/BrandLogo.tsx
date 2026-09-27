import Link from "next/link";
import Image from "next/image";

/* ==========================================================================
   Design System V2 — Brand
   The official ICT Funded EA Pro logo asset (never redesigned or recolored).
   The artwork is dark navy on a transparent background, so in dark surfaces
   it renders inside a white chip; use variant="plain" only on light
   backgrounds.
   ========================================================================== */

export interface BrandLogoProps {
  href?: string;
  variant?: "chip" | "plain";
  height?: number;
  className?: string;
}

export function BrandLogo({ href = "/", variant = "chip", height = 28, className = "" }: BrandLogoProps) {
  const img = (
    <Image
      src="/logo.png"
      alt="ICT Funded EA Pro"
      width={height * (634 / 410)}
      height={height}
      priority
      className={variant === "chip" ? "h-full w-auto" : "h-full w-auto"}
      style={{ height: "100%", width: "auto" }}
    />
  );

  const content =
    variant === "chip" ? (
      <span
        className="ds-chip-logo"
        style={{ height: height + 12, borderRadius: 10 }}
        role="img"
        aria-label="ICT Funded EA Pro"
      >
        {img}
      </span>
    ) : (
      <span className="inline-flex" style={{ height }}>
        {img}
      </span>
    );

  return (
    <Link href={href} className={`inline-flex items-center shrink-0 ${className}`} aria-label="ICT Funded EA Pro — Home">
      {content}
    </Link>
  );
}
