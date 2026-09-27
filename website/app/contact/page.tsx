import type { Metadata } from "next";
import CTASection from "@/components/content/CTASection";
import PageHero from "@/components/content/PageHero";
import Icon from "@/components/primitives/Icon";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Contact the ICT Funded EA Pro support team by email or Telegram. We help with activation, platform setup, funded-rule configuration, and troubleshooting.",
};

const supportEmail = "support@ictfundedeapro.com";
const telegramHandle = "@ict_funded_pro_ea_bot";

export default function ContactPage() {
  return (
    <>
      <PageHero
        eyebrow="Contact"
        title="We answer quickly, and we answer thoroughly."
        description="Activation, platform setup, funded-rule configuration, or troubleshooting — reach us on the channel that suits you. All plans include email support; Premium and Enterprise include priority channels."
        align="center"
      />

      <section className="section" aria-labelledby="contact-channels-title">
        <div className="container">
          <h2 className="sr-only" id="contact-channels-title">Contact channels</h2>
          <div className="contact-grid">
            <div className="contact-card">
              <h3 className="contact-card__title">Support channels</h3>
              <p className="contact-card__description">
                Choose the channel that fits the urgency. For anything account-specific, please
                send it from the registered email so we can verify your subscription.
              </p>
              <div className="contact-channel">
                <span className="contact-channel__icon"><Icon name="mail" size={20} /></span>
                <div>
                  <span className="contact-channel__label">Email support</span>
                  <a className="contact-channel__value" href={`mailto:${supportEmail}`}>{supportEmail}</a>
                  <span className="contact-channel__hint">Replies within one business day on all plans.</span>
                </div>
              </div>
              <div className="contact-channel">
                <span className="contact-channel__icon"><Icon name="send" size={20} /></span>
                <div>
                  <span className="contact-channel__label">Telegram</span>
                  <a className="contact-channel__value" href={`https://t.me/${telegramHandle.slice(1)}`}>{telegramHandle}</a>
                  <span className="contact-channel__hint">Fastest for activation and setup questions. Do not share account passwords.</span>
                </div>
              </div>
              <div className="contact-channel">
                <span className="contact-channel__icon"><Icon name="clock" size={20} /></span>
                <div>
                  <span className="contact-channel__label">Support hours</span>
                  <span className="contact-channel__value">Monday to Friday, 09:00–18:00 UTC</span>
                  <span className="contact-channel__hint">Enterprise plan includes 24/7 support.</span>
                </div>
              </div>
            </div>

            <div className="contact-card">
              <h3 className="contact-card__title">Before you write</h3>
              <p className="contact-card__description">
                Most account-specific questions are resolved faster in the client dashboard:
              </p>
              <ul className="pricing-card__features" style={{ marginBottom: 0 }}>
                <li><Icon name="check" size={16} /> License and plan status</li>
                <li><Icon name="check" size={16} /> Linked accounts and verification state</li>
                <li><Icon name="check" size={16} /> Funded-rule and risk-limit settings</li>
                <li><Icon name="check" size={16} /> Download links for MT4 and MT5</li>
              </ul>
              <div className="callout callout--warning" style={{ marginTop: 18 }}>
                <span className="callout__title">Security note</span>
                Our team will never ask for your broker password, your MetaTrader investor password,
                or your license key in chat. Report any such request to support immediately.
              </div>
            </div>
          </div>
        </div>
      </section>

      <CTASection
        title="Not a client yet?"
        description="Create your account and get the engine protecting your funded account today."
      />
    </>
  );
}
