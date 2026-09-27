import type { Metadata } from "next";
import LinkButton from "@/components/primitives/LinkButton";
import { portalUrls } from "@/lib/urls";

export const metadata: Metadata = {
  title: "Page not found",
  description: "The page you are looking for does not exist.",
};

export default function NotFound() {
  return (
    <div className="page-hero page-hero--center">
      <div className="container">
        <p className="eyebrow">404</p>
        <h1 className="page-hero__title">This page does not exist.</h1>
        <p className="page-hero__description">
          The link may be outdated or the address was typed incorrectly. Head back to the home
          page or open your client portal.
        </p>
        <div className="cta-section__actions">
          <LinkButton href="/" variant="primary">
            Back to home
          </LinkButton>
          <LinkButton href={portalUrls.clientLogin} variant="secondary">
            Client portal
          </LinkButton>
        </div>
      </div>
    </div>
  );
}
