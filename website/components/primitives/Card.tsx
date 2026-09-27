import type { HTMLAttributes } from "react";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  padded?: boolean;
  elevated?: boolean;
  interactive?: boolean;
};

export default function Card({
  padded = true,
  elevated = false,
  interactive = false,
  className = "",
  ...props
}: CardProps) {
  const modifiers = [
    "card",
    padded && "card--padded",
    elevated && "card--elevated",
    interactive && "card--interactive",
    className,
  ].filter(Boolean).join(" ");
  return <div className={modifiers} {...props} />;
}
