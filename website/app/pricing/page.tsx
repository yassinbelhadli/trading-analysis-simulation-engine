import type { Metadata } from "next";
import CTASection from "@/components/content/CTASection";
import PageHero from "@/components/content/PageHero";
import RiskDisclaimer from "@/components/content/RiskDisclaimer";
import SectionHeading from "@/components/content/SectionHeading";
import PricingCard from "@/components/commerce/PricingCard";
import Icon from "@/components/primitives/Icon";
import { portalUrls } from "@/lib/urls";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Four plans for ICT Funded EA Pro — Starter, Professional, Premium, and Enterprise. Prices and limits match what is enforced in your client portal. Built for funded-account traders.",
};

// NOTE: plan names, prices, and account limits must mirror the backend
// source of truth (api/services/plans_config.py). The client portal renders
// these plans dynamically — keep this page in sync.
const plans = [
  {
    name: "Starter",
    price: "$29",
    billingLabel: "per month, billed monthly",
    accountLimit: "1 funded account",
    features: [
      "ICT / SMC trading engine",
      "Funded-rule compliance",
      "Daily loss and drawdown limits",
      "Profit target and trading days",
      "XAUUSD and NAS100",
      "Telegram trade alerts",
    ],
    href: portalUrls.clientRegister,
    featured: false,
  },
  {
    name: "Professional",
    price: "$59",
    billingLabel: "per month, billed monthly",
    accountLimit: "Up to 3 funded accounts",
    features: [
      "Everything in Starter",
      "Multi-account management",
      "Per-account rule sets",
      "Performance analytics",
      "Email support",
    ],
    href: portalUrls.clientRegister,
    featured: false,
  },
  {
    name: "Premium",
    price: "$99",
    billingLabel: "per month, billed monthly",
    accountLimit: "Up to 10 funded accounts",
    features: [
      "Everything in Professional",
      "API access",
      "Priority support",
      "Highest risk and account limits",
    ],
    href: portalUrls.clientRegister,
    featured: true,
  },
  {
    name: "Enterprise",
    price: "$999",
    billingLabel: "one-time license",
    accountLimit: "Unlimited funded accounts",
    features: [
      "Everything in Premium",
      "Unlimited accounts",
      "Dedicated onboarding",
      "24/7 support",
    ],
    href: portalUrls.clientRegister,
    featured: false,
  },
];

const comparisonRows = [
  { feature: "Funded accounts", starter: "1", professional: "3", premium: "10", enterprise: "999+" },
  { feature: "ICT / SMC engine", starter: true, professional: true, premium: true, enterprise: true },
  { feature: "Daily loss limit", starter: true, professional: true, premium: true, enterprise: true },
  { feature: "Maximum drawdown", starter: true, professional: true, premium: true, enterprise: true },
  { feature: "Profit target tracking", starter: true, professional: true, premium: true, enterprise: true },
  { feature: "Trading days compliance", starter: true, professional: true, premium: true, enterprise: true },
  { feature: "XAUUSD and NAS100", starter: true, professional: true, premium: true, enterprise: true },
  { feature: "Telegram alerts", starter: true, professional: true, premium: true, enterprise: true },
  { feature: "Multi-account dashboard", starter: false, professional: true, premium: true, enterprise: true },
  { feature: "Performance analytics", starter: false, professional: true, premium: true, enterprise: true },
  { feature: "API access", starter: false, professional: false, premium: true, enterprise: true },
  { feature: "Priority support", starter: false, professional: false, premium: true, enterprise: true },
];

function ComparisonValue({ value }: { value: boolean | string }) {
  if (value === true) return <Icon name="check" size={18} label="Included" />;
  if (value === false) return <span className="compare__no">—</span>;
  return <span>{value}</span>;
}

export default function PricingPage() {
  return (
    <>
      <PageHero
        eyebrow="Pricing"
        title="Simple pricing for serious account protection."
        description="One subscription covers the EA, the client dashboard, and Telegram alerts. No hidden fees, no per-trade costs — cancel anytime."
        align="center"
      />

      <section className="section" aria-labelledby="plans-title">
        <div className="container">
          <h2 className="sr-only" id="plans-title">Subscription plans</h2>
          <div className="pricing-grid">
            {plans.map((plan) => <PricingCard key={plan.name} {...plan} />)}
          </div>
          <p className="pricing-note">
            Prefer a one-time license? The Enterprise plan is a single one-time payment of $999.
            Plans and limits are managed from your client portal.
          </p>
        </div>
      </section>

      <section className="section" aria-labelledby="compare-title">
        <div className="container">
          <SectionHeading
            eyebrow="Compare plans"
            title="Every tier protects your funded account."
            description="The differences are scope — the risk and compliance engine is identical across all plans."
            align="center"
          />
          <h2 className="sr-only" id="compare-title">Plan comparison table</h2>
          <div className="compare">
            <table className="compare__table">
              <thead>
                <tr>
                  <th scope="col">Feature</th>
                  <th scope="col">Starter</th>
                  <th scope="col">Professional</th>
                  <th scope="col">Premium</th>
                  <th scope="col">Enterprise</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row.feature}>
                    <td>{row.feature}</td>
                    <td><ComparisonValue value={row.starter} /></td>
                    <td><ComparisonValue value={row.professional} /></td>
                    <td><ComparisonValue value={row.premium} /></td>
                    <td><ComparisonValue value={row.enterprise} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="section section--tight" aria-labelledby="funded-note-title">
        <div className="container">
          <div className="callout callout--warning">
            <span className="callout__title" id="funded-note-title">Funded-program compatibility</span>
            ICT Funded EA Pro is designed for funded programs that allow expert advisors on MT4/MT5.
            Funded-account rules differ between programs — always confirm that automated trading is
            permitted on your account and configure the EA limits to match your program before
            activation. Some proprietary firms restrict specific strategies, symbols, or times.
          </div>
        </div>
      </section>

      <section className="section section--tight">
        <div className="container">
          <RiskDisclaimer />
        </div>
      </section>

      <CTASection
        title="Start protecting your funded account today."
        description="Choose a plan during registration and get your license validated before the engine touches a single trade."
      />
    </>
  );
}
