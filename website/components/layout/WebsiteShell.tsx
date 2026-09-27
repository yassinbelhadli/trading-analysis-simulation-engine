import type { ReactNode } from "react";
import WebsiteFooter from "@/components/layout/WebsiteFooter";
import WebsiteHeader from "@/components/layout/WebsiteHeader";

export default function WebsiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="website-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <WebsiteHeader />
      <main id="main-content">{children}</main>
      <WebsiteFooter />
    </div>
  );
}
