import type { Metadata } from "next";
import CTASection from "@/components/content/CTASection";
import FeatureCard from "@/components/content/FeatureCard";
import FeatureGrid from "@/components/content/FeatureGrid";
import PageHero from "@/components/content/PageHero";
import RiskDisclaimer from "@/components/content/RiskDisclaimer";
import SectionHeading from "@/components/content/SectionHeading";
import Icon from "@/components/primitives/Icon";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Explore the ICT/SMC trading engine, funded-rule compliance, risk management, news and spread filters, MT4/MT5 support, Telegram integration, and the client dashboard.",
};

const engineFeatures = [
  {
    icon: "layers" as const,
    title: "Market structure",
    description: "Identifies break of structure (BOS) and change of character (CHoCH) across the session.",
  },
  {
    icon: "activity" as const,
    title: "Liquidity",
    description: "Maps equal highs, equal lows, and key price levels where liquidity rests.",
  },
  {
    icon: "chart" as const,
    title: "Fair value gaps (FVG)",
    description: "Tracks displaced candles and their imbalance zones for high-probability entries.",
  },
  {
    icon: "bolt" as const,
    title: "Order blocks",
    description: "Detects institutional order blocks and sweeps before entries are considered.",
  },
  {
    icon: "check-circle" as const,
    title: "Confirmation",
    description: "No trade fires on structure alone — a confirming signal must align with the bias.",
  },
  {
    icon: "gauge" as const,
    title: "Time and session filters",
    description: "Focus on liquidity windows and avoid low-quality sessions with configurable hours.",
  },
];

const riskFeatures = [
  {
    icon: "shield" as const,
    title: "Daily loss limit",
    description: "Stops trading for the day once your configured daily loss is reached — before the program enforces it.",
  },
  {
    icon: "gauge" as const,
    title: "Maximum drawdown",
    description: "Tracks balance and equity drawdown against your funded-program maximum and halts trading on approach.",
  },
  {
    icon: "check-circle" as const,
    title: "Profit target",
    description: "Optionally locks in trading once your profit target is reached, preserving the result.",
  },
  {
    icon: "clock" as const,
    title: "Trading days compliance",
    description: "Tracks minimum trading days and avoids actions that would violate program requirements.",
  },
  {
    icon: "shield" as const,
    title: "Hard stops on every trade",
    description: "Every position opens with a stop loss and a configured risk per trade — no discretionary exits.",
  },
  {
    icon: "monitor" as const,
    title: "Breakeven management",
    description: "Moves stops to breakeven after configurable profit thresholds and trails on strong moves.",
  },
];

const platformFeatures = [
  {
    icon: "layers" as const,
    title: "MetaTrader 4",
    description: "Full EA support on MT4 with the same engine logic as MT5 — no feature gaps between platforms.",
  },
  {
    icon: "database" as const,
    title: "MetaTrader 5",
    description: "Native MT5 build with faster execution and the same rule engine, parameters, and alerts.",
  },
  {
    icon: "bolt" as const,
    title: "Automatic platform detection",
    description: "The EA detects the terminal on first load and applies the correct internal layout automatically.",
  },
  {
    icon: "user" as const,
    title: "Account type aware",
    description: "Inputs adapt to raw, standard, and cent account types, including digit and symbol mapping.",
  },
];

const workflowFeatures = [
  {
    icon: "bell" as const,
    title: "News filter",
    description: "High-impact economic releases pause trading automatically, with a configurable window before and after each event.",
  },
  {
    icon: "activity" as const,
    title: "Spread filter",
    description: "Blocks entries when the live spread exceeds your maximum, protecting funded accounts during volatile markets.",
  },
  {
    icon: "send" as const,
    title: "Telegram integration",
    description: "Fills, rule warnings, risk stops, and connection status delivered to your Telegram in real time.",
  },
  {
    icon: "monitor" as const,
    title: "Client dashboard",
    description: "See every linked account, its rule status, open positions, and license details in one place.",
  },
  {
    icon: "key" as const,
    title: "License and activation",
    description: "Licenses are validated before activation, and expired licenses disable trading with a clear notification.",
  },
  {
    icon: "users" as const,
    title: "Multi-account support",
    description: "Run several funded accounts under one subscription, each with its own rule set and limits.",
  },
];

export default function FeaturesPage() {
  return (
    <>
      <PageHero
        eyebrow="Features"
        title="A trading engine that puts capital protection first."
        description="ICT Funded EA Pro is a complete workflow for funded-account traders: a strict ICT/SMC engine, a funded-rule compliance layer, and a risk engine that acts before the market does."
      />

      <section className="section" aria-labelledby="engine-title">
        <div className="container">
          <SectionHeading
            eyebrow="ICT / SMC engine"
            title="Entries built on structure, not guesswork."
            description="Every setup must clear the full market-structure pipeline before a single order is considered."
          />
          <h2 className="sr-only" id="engine-title">ICT and SMC trading engine</h2>
          <FeatureGrid>
            {engineFeatures.map((feature) => <FeatureCard key={feature.title} {...feature} />)}
          </FeatureGrid>
        </div>
      </section>

      <section className="section" aria-labelledby="risk-title">
        <div className="container">
          <SectionHeading
            eyebrow="Risk management"
            title="Funded rules enforced before the trade, not after."
            description="The risk engine monitors your balance, equity, and open exposure against your program limits at all times."
          />
          <h2 className="sr-only" id="risk-title">Risk management</h2>
          <FeatureGrid>
            {riskFeatures.map((feature) => <FeatureCard key={feature.title} {...feature} />)}
          </FeatureGrid>
          <div className="callout callout--warning" style={{ marginTop: 18 }}>
            <span className="callout__title">Rule violations stop trading</span>
            If a funded rule is approached or violated, the engine stops opening new trades, closes
            risk positions when configured, and notifies you immediately. Capital protection has
            priority over opportunity.
          </div>
        </div>
      </section>

      <section className="section" aria-labelledby="platform-title">
        <div className="container">
          <SectionHeading
            eyebrow="Platforms"
            title="MetaTrader 4 and MetaTrader 5, one engine."
            description="Support for both terminals is not an afterthought. The same rules, the same alerts, and the same risk layer on either platform."
          />
          <h2 className="sr-only" id="platform-title">MetaTrader 4 and 5 support</h2>
          <FeatureGrid>
            {platformFeatures.map((feature) => <FeatureCard key={feature.title} {...feature} />)}
          </FeatureGrid>
        </div>
      </section>

      <section className="section" aria-labelledby="workflow-title">
        <div className="container">
          <SectionHeading
            eyebrow="Monitoring and control"
            title="From market filters to your pocket."
            description="The rest of the ecosystem keeps you informed and in control without adding manual work."
          />
          <h2 className="sr-only" id="workflow-title">Workflow features</h2>
          <FeatureGrid>
            {workflowFeatures.map((feature) => <FeatureCard key={feature.title} {...feature} />)}
          </FeatureGrid>
          <div className="split" style={{ marginTop: 48 }}>
            <div className="split__content">
              <h3 className="section-heading__title">News and spread filters run silently in the background</h3>
              <p className="section-heading__description">
                High-impact events and abnormal spreads are the two most common ways funded accounts
                get breached by an automated system. ICT Funded EA Pro treats both as first-class
                protections with configurable thresholds.
              </p>
              <ul className="split__list">
                <li className="split__item"><Icon name="check" size={18} /> Auto-pause around high-impact releases</li>
                <li className="split__item"><Icon name="check" size={18} /> Max-spread guard before every entry</li>
                <li className="split__item"><Icon name="check" size={18} /> Resume conditions fully configurable</li>
              </ul>
            </div>
            <div className="split__visual">
              <div className="mock" aria-hidden="true">
                <div className="mock__bar">
                  <span className="mock__dot" />
                  <span className="mock__dot" />
                  <span className="mock__dot" />
                  <span className="mock__pill">News pause on</span>
                </div>
                <div className="mock__row mock__row--green" />
                <div className="mock__row mock__row--blue mock__row--short" />
                <div className="mock__row mock__row--blue mock__row--third" />
                <div className="mock__grid">
                  <div className="mock__cell"><span className="mock__cell-value">High impact</span><span className="mock__cell-label">Paused</span></div>
                  <div className="mock__cell"><span className="mock__cell-value">Spread</span><span className="mock__cell-label">Filtered</span></div>
                  <div className="mock__cell"><span className="mock__cell-value">Engine</span><span className="mock__cell-label">Standing by</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section section--tight">
        <div className="container">
          <RiskDisclaimer />
        </div>
      </section>

      <CTASection
        title="Put the protection layer to work on your account."
        description="Create your account, link your MetaTrader terminal, and review the funded-rule settings before the engine takes its first trade."
      />
    </>
  );
}
