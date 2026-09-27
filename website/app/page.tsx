import type { Metadata } from "next";
import CTASection from "@/components/content/CTASection";
import FeatureCard from "@/components/content/FeatureCard";
import FeatureGrid from "@/components/content/FeatureGrid";
import SectionHeading from "@/components/content/SectionHeading";
import StatsStrip from "@/components/content/StatsStrip";
import Icon from "@/components/primitives/Icon";
import LinkButton from "@/components/primitives/LinkButton";
import Logo from "@/components/primitives/Logo";
import { portalUrls } from "@/lib/urls";

export const metadata: Metadata = {
  title: "Funded Account Trading EA",
  description:
    "ICT Funded EA Pro is a disciplined algorithmic trading EA for funded-account traders. Market-structure execution, funded-rule compliance, and capital protection on MetaTrader 4 and 5.",
};

const stats = [
  { value: "MT4 + MT5", label: "Supported platforms" },
  { value: "12+", label: "Protective filters per setup" },
  { value: "24/7", label: "Funded-rule monitoring" },
  { value: "0", label: "Martingale or grid strategies" },
];

const steps = [
  {
    title: "Create your account",
    description: "Register in the client portal, choose a plan, and activate your license.",
  },
  {
    title: "Link your MetaTrader account",
    description: "Connect MT4 or MT5 and complete the short verification checklist.",
  },
  {
    title: "Configure your funded rules",
    description: "Set daily loss, drawdown, and profit-target limits to match your program.",
  },
  {
    title: "Trade with discipline",
    description: "The engine follows ICT/SMC setups while the risk layer guards your account.",
  },
];

const features = [
  {
    icon: "chart" as const,
    title: "SMC / ICT trading engine",
    description: "Market structure, liquidity, fair value gaps, order blocks, and confirmation filters precede every entry.",
  },
  {
    icon: "shield" as const,
    title: "Funded-rule compliance",
    description: "Daily loss, maximum drawdown, profit target, and trading-day limits enforced before each trade.",
  },
  {
    icon: "gauge" as const,
    title: "Risk engine",
    description: "Hard stops, breakeven management, and position sizing calculated from your account balance.",
  },
  {
    icon: "bell" as const,
    title: "News filter",
    description: "Trading pauses automatically around high-impact economic releases.",
  },
  {
    icon: "layers" as const,
    title: "MT4 and MT5",
    description: "One engine, both platforms — the platform is detected automatically during setup.",
  },
  {
    icon: "send" as const,
    title: "Telegram notifications",
    description: "Trade fills, rule warnings, and risk stops pushed to your phone in real time.",
  },
];

const testimonials = [
  {
    quote:
      "The funded-rule automation is what convinced me. Daily loss, drawdown, and profit target are enforced before the trade, not after. It removed the emotional part of my sessions.",
    name: "Amira K.",
    role: "Funded forex trader, 100k account",
    initials: "AK",
  },
  {
    quote:
      "I run the same engine on MT4 and MT5 with a single dashboard and Telegram alerts. It took the manual routine out of my evenings and kept my account inside program limits.",
    name: "Marco T.",
    role: "Part-time trader",
    initials: "MT",
  },
  {
    quote:
      "Every entry was a real market-structure setup — no revenge trading, no doubling down. The news filter held my daily loss limit steady during the last major release week.",
    name: "Daniel R.",
    role: "Prop challenge participant",
    initials: "DR",
  },
];

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <div className="container">
          <div className="hero__inner">
            <div className="hero__logo">
              <Logo compact />
            </div>
            <p className="hero__badge">Algorithmic trading for funded accounts</p>
            <h1 className="hero__title">Trade your funded account with market structure and discipline.</h1>
            <p className="hero__subhead">
              ICT Funded EA Pro combines a strict ICT/SMC trading engine with a funded-rule
              compliance layer, so your daily loss, drawdown, and profit target are protected
              on every MetaTrader session — automatically.
            </p>
            <div className="hero__actions">
              <LinkButton href={portalUrls.clientRegister} size="large">
                Create account <Icon name="arrow-up-right" size={17} />
              </LinkButton>
              <LinkButton href={portalUrls.clientLogin} variant="secondary" size="large">
                Client login
              </LinkButton>
            </div>
            <p className="hero__note">Activation requires license validation. No martingale, no grid, no hedge strategies.</p>
          </div>
        </div>
      </section>

      <section className="section section--tight" aria-label="Product highlights">
        <div className="container">
          <StatsStrip items={stats} />
        </div>
      </section>

      <section className="section" aria-labelledby="how-it-works-title">
        <div className="container">
          <SectionHeading
            eyebrow="How it works"
            title="From registration to disciplined trading in four steps."
            description="No manual trade journaling and no after-the-fact fixes. The rules are configured once and enforced continuously."
            align="center"
          />
          <h2 className="sr-only" id="how-it-works-title">How it works</h2>
          <div className="steps">
            {steps.map((step, index) => (
              <div className="steps__item" key={step.title}>
                <span className="steps__number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                <h3 className="steps__title">{step.title}</h3>
                <p className="steps__description">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="highlights-title">
        <div className="container">
          <SectionHeading
            eyebrow="Why ICT Funded EA Pro"
            title="Capital protection before profit — on every trade."
            description="Every decision passes through the ICT/SMC engine and a stack of funded-rule and risk filters before a single order is placed."
            align="center"
          />
          <h2 className="sr-only" id="highlights-title">Feature highlights</h2>
          <FeatureGrid>
            {features.map((feature) => <FeatureCard key={feature.title} {...feature} />)}
          </FeatureGrid>
        </div>
      </section>

      <section className="section" aria-labelledby="product-title">
        <div className="container">
          <SectionHeading
            eyebrow="The complete product"
            title="An EA, a dashboard, and instant notifications."
            description="One subscription covers the full workflow — from MetaTrader execution to monitoring and alerts."
            align="center"
          />
          <h2 className="sr-only" id="product-title">Product overview</h2>
          <div className="split">
            <div className="split__content">
              <h3 className="section-heading__title">Expert advisor for MetaTrader 4 and 5</h3>
              <p className="section-heading__description">
                A single EA installs on MT4 and MT5. The platform is detected automatically, and
                every parameter is configurable from the chart — no external bridging required.
              </p>
              <ul className="split__list">
                <li className="split__item"><Icon name="check" size={18} /> Platform auto-detection on first load</li>
                <li className="split__item"><Icon name="check" size={18} /> Configurable inputs mapped to your broker account type</li>
                <li className="split__item"><Icon name="check" size={18} /> Works with account types that allow expert advisors</li>
              </ul>
            </div>
            <div className="split__visual">
              <div className="mock" aria-hidden="true">
                <div className="mock__bar">
                  <span className="mock__dot" />
                  <span className="mock__dot" />
                  <span className="mock__dot" />
                  <span className="mock__pill">EA active</span>
                </div>
                <div className="mock__row mock__row--green" />
                <div className="mock__row mock__row--blue" />
                <div className="mock__row mock__row--green mock__row--short" />
                <div className="mock__row mock__row--blue mock__row--third" />
                <div className="mock__grid">
                  <div className="mock__cell"><span className="mock__cell-value">Daily loss</span><span className="mock__cell-label">Protected</span></div>
                  <div className="mock__cell"><span className="mock__cell-value">Drawdown</span><span className="mock__cell-label">Tracked</span></div>
                  <div className="mock__cell"><span className="mock__cell-value">Target</span><span className="mock__cell-label">On plan</span></div>
                </div>
              </div>
            </div>
          </div>
          <div className="split split--reverse">
            <div className="split__content">
              <h3 className="section-heading__title">Client dashboard and Telegram</h3>
              <p className="section-heading__description">
                Monitor every linked account in the client portal and receive the same state on
                Telegram — trade fills, limit warnings, and risk stops.
              </p>
              <ul className="split__list">
                <li className="split__item"><Icon name="check" size={18} /> Per-account rule status and open positions</li>
                <li className="split__item"><Icon name="check" size={18} /> Instant Telegram alerts for fills and risk events</li>
                <li className="split__item"><Icon name="check" size={18} /> License and plan management in one place</li>
              </ul>
            </div>
            <div className="split__visual">
              <div className="mock" aria-hidden="true">
                <div className="mock__bar">
                  <span className="mock__dot" />
                  <span className="mock__dot" />
                  <span className="mock__dot" />
                  <span className="mock__pill">Alerts on</span>
                </div>
                <div className="mock__row mock__row--blue" />
                <div className="mock__row mock__row--green mock__row--third" />
                <div className="mock__row mock__row--blue mock__row--short" />
                <div className="mock__grid">
                  <div className="mock__cell"><span className="mock__cell-value">Trade opened</span><span className="mock__cell-label">Alerted</span></div>
                  <div className="mock__cell"><span className="mock__cell-value">Rule check</span><span className="mock__cell-label">Cleared</span></div>
                  <div className="mock__cell"><span className="mock__cell-value">Risk stop</span><span className="mock__cell-label">Armed</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="testimonials-title">
        <div className="container">
          <SectionHeading
            eyebrow="Traders on the engine"
            title="Built for funded-account traders."
            description="Professional experiences with the same rules-first workflow."
            align="center"
          />
          <h2 className="sr-only" id="testimonials-title">Testimonials</h2>
          <div className="testimonials">
            {testimonials.map((testimonial) => (
              <figure className="testimonial" key={testimonial.name}>
                <blockquote className="testimonial__quote">&ldquo;{testimonial.quote}&rdquo;</blockquote>
                <figcaption className="testimonial__footer">
                  <span className="testimonial__avatar" aria-hidden="true">{testimonial.initials}</span>
                  <span>
                    <span className="testimonial__name">{testimonial.name}</span>
                    <span className="testimonial__role">{testimonial.role}</span>
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      </section>

      <CTASection />
    </>
  );
}
