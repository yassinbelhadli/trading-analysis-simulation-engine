import Link from "next/link";
import type { AnchorHTMLAttributes } from "react";

type LinkButtonProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
  variant?: "primary" | "secondary" | "ghost";
  size?: "small" | "medium" | "large";
};

export default function LinkButton({
  href,
  variant = "primary",
  size = "medium",
  className = "",
  children,
  ...props
}: LinkButtonProps) {
  const classes = `button button--${variant} button--${size} ${className}`.trim();
  if (href.startsWith("http")) {
    return <a className={classes} href={href} {...props}>{children}</a>;
  }
  return <Link className={classes} href={href} {...props}>{children}</Link>;
}
