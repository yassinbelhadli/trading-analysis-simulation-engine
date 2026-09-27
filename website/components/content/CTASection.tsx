import LinkButton from "@/components/primitives/LinkButton";
import { portalUrls } from "@/lib/urls";

type CTASectionProps = {
  title?: string;
  description?: string;
};

export default function CTASection({
  title = "Ready to trade your funded account with discipline?",
  description =
    "Create your account, link your MetaTrader terminal, and let the engine follow market structure while the risk layer protects your capital.",
}: CTASectionProps) {
  return (
    <section className="cta" aria-labelledby="cta-title">
      <div className="container">
        <div className="cta__inner">
          <h2 id="cta-title" className="cta__title">{title}</h2>
          <p className="cta__description">{description}</p>
          <div className="cta__actions">
            <LinkButton href={portalUrls.clientRegister} size="large">Create account</LinkButton>
            <LinkButton href={portalUrls.clientLogin} variant="secondary" size="large">Client login</LinkButton>
          </div>
          <p className="cta__note">
            Compatible with major funded programs that allow MT4/MT5 expert advisors. Always review your program rules before use.
          </p>
        </div>
      </div>
    </section>
  );
}
