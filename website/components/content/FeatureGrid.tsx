import type { ReactNode } from "react";

export default function FeatureGrid({ children }: { children: ReactNode }) {
  return <div className="feature-grid">{children}</div>;
}
