import type { Metadata } from "next";
import CTASection from "@/components/content/CTASection";
import PageHero from "@/components/content/PageHero";
import SectionHeading from "@/components/content/SectionHeading";
import Icon from "@/components/primitives/Icon";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "Get started with ICT Funded EA Pro: installation on MetaTrader 4 and 5, account linking, funded-rule and risk-limit configuration, and a full explanation of the EA settings.",
};

const hubCards = [
  {
    icon: "bolt" as const,
    title: "Getting started",
    description: "Account creation, license activation, and the activation checklist.",
    href: "#getting-started",
  },
  {
    icon: "database" as const,
    title: "Platform installation",
    description: "Installing and configuring the EA on MetaTrader 4 and MetaTrader 5.",
    href: "#installation",
  },
  {
    icon: "layers" as const,
    title: "Account linking",
    description: "Connecting your funded account and passing the verification checklist.",
    href: "#account-linking",
  },
  {
    icon: "gauge" as const,
    title: "Funded rules and risk limits",
    description: "Mapping your program's rules to the EA's daily loss, drawdown, and target settings.",
    href: "#funded-rules",
  },
  {
    icon: "monitor" as const,
    title: "EA settings explained",
    description: "Every input parameter, from structure filters to risk and session controls.",
    href: "#ea-settings",
  },
  {
    icon: "message" as const,
    title: "Support and FAQ",
    description: "Troubleshooting, common questions, and how to reach the support team.",
    href: "#support",
  },
];

export default function DocsPage() {
  return (
    <>
      <PageHero
        eyebrow="Documentation"
        title="Everything you need to run the engine safely."
        description="Follow the setup order below — account, license, platform, rules, settings — and the engine will never activate before your verification is complete."
      />

      <section className="section section--tight" aria-labelledby="docs-hub-title">
        <div className="container">
          <SectionHeading
            eyebrow="Documentation hub"
            title="Jump to a topic."
            description="Each guide is self-contained. New traders should start with Getting started."
          />
          <h2 className="sr-only" id="docs-hub-title">Documentation topics</h2>
          <div className="docs-grid">
            {hubCards.map((card) => (
              <div className="docs-card" key={card.href}>
                <span className="docs-card__icon"><Icon name={card.icon} size={20} /></span>
                <h3 className="docs-card__title">{card.title}</h3>
                <p className="docs-card__description">{card.description}</p>
                <a className="docs-card__link" href={card.href}>
                  Read guide <Icon name="arrow-up-right" size={16} />
                </a>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section docs-section" id="getting-started" aria-labelledby="getting-started-title">
        <div className="container">
          <SectionHeading
            eyebrow="Guide 01"
            title="Getting started"
            description="From registration to a validated, ready-to-activate license."
          />
          <h2 className="sr-only" id="getting-started-title">Getting started</h2>
          <div className="docs-section__body">
            <div className="doc-block">
              <h3 className="doc-block__title">1. Create your account</h3>
              <div className="doc-block__body">
                <p>Register in the client portal and choose a plan. You will receive a license key and access to the download page for your platform.</p>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">2. Activate your license</h3>
              <div className="doc-block__body">
                <p>The EA validates the license during installation. Activation only completes with a valid, non-expired key. If a license expires, trading is disabled and you are notified in the dashboard and on Telegram.</p>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">3. Complete the activation checklist</h3>
              <div className="doc-block__body">
                <p>Before trading is enabled, verify credentials, broker, account type, balance, funded rules, available symbols, and trading permissions. The engine will not activate trading until verification passes.</p>
              </div>
            </div>
            <div className="callout callout--info">
              <span className="callout__title">Next steps</span>
              Install the EA on your platform, then configure your funded rules and risk limits before enabling automatic trading.
            </div>
          </div>
        </div>
      </section>

      <section className="section docs-section" id="installation" aria-labelledby="installation-title">
        <div className="container">
          <SectionHeading
            eyebrow="Guide 02"
            title="Platform installation"
            description="Installing the same engine on MetaTrader 4 and MetaTrader 5."
          />
          <h2 className="sr-only" id="installation-title">Platform installation</h2>
          <div className="docs-section__body">
            <div className="doc-block">
              <h3 className="doc-block__title">MetaTrader 4</h3>
              <div className="doc-block__body">
                <ol>
                  <li>Download the EA package from the client portal.</li>
                  <li>Open MT4 and choose File &gt; Open Data Folder from the menu.</li>
                  <li>Place the EA file into the <strong>MQL4/Experts</strong> folder and restart the terminal.</li>
                  <li>Drag the EA onto a chart, accept auto-trading permissions, and set your inputs.</li>
                </ol>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">MetaTrader 5</h3>
              <div className="doc-block__body">
                <ol>
                  <li>Download the EA package from the client portal.</li>
                  <li>Open MT5 and choose File &gt; Open Data Folder from the menu.</li>
                  <li>Place the EA file into the <strong>MQL5/Experts</strong> folder and restart the terminal.</li>
                  <li>Attach the EA to a chart and confirm that <strong>Algo Trading</strong> is enabled in the toolbar.</li>
                </ol>
              </div>
            </div>
            <div className="callout callout--warning">
              <span className="callout__title">Auto-trading must be enabled</span>
              The EA requires algorithmic trading permission from the terminal and your broker account. Confirm with your broker that automated EAs are allowed before going live.
            </div>
          </div>
        </div>
      </section>

      <section className="section docs-section" id="account-linking" aria-labelledby="account-linking-title">
        <div className="container">
          <SectionHeading
            eyebrow="Guide 03"
            title="Account linking"
            description="Connect your funded account and confirm it is safe to trade."
          />
          <h2 className="sr-only" id="account-linking-title">Account linking</h2>
          <div className="docs-section__body">
            <div className="doc-block">
              <h3 className="doc-block__title">Link your account in the dashboard</h3>
              <div className="doc-block__body">
                <p>Enter your account identifier in the client dashboard. The dashboard verifies the broker, account type, balance, and available symbols. Credentials and sensitive account details are encrypted before storage.</p>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">Verification checklist</h3>
              <div className="doc-block__body">
                <ul>
                  <li>Broker and server reachable from the terminal</li>
                  <li>Account type supported (standard, raw, or cent)</li>
                  <li>Balance sufficient for your risk plan</li>
                  <li>Automated trading permission enabled</li>
                  <li>Required symbols available on the account</li>
                </ul>
              </div>
            </div>
            <div className="callout callout--danger">
              <span className="callout__title">Never trade before verification</span>
              The engine is designed never to activate trading before the verification checklist passes. If any check fails, trading stays disabled and you are notified.
            </div>
          </div>
        </div>
      </section>

      <section className="section docs-section" id="funded-rules" aria-labelledby="funded-rules-title">
        <div className="container">
          <SectionHeading
            eyebrow="Guide 04"
            title="Funded rules and risk limits"
            description="Map your program's rules to the engine's protection layer."
          />
          <h2 className="sr-only" id="funded-rules-title">Funded rules and risk limits</h2>
          <div className="docs-section__body">
            <div className="doc-block">
              <h3 className="doc-block__title">Daily loss limit</h3>
              <div className="doc-block__body">
                <p>Set the maximum allowed loss for the day. When reached, the engine stops opening new trades for that session and notifies you.</p>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">Maximum drawdown</h3>
              <div className="doc-block__body">
                <p>Configure both balance and equity drawdown limits. The engine tracks the higher-risk measure and halts trading as the limit is approached.</p>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">Profit target and trading days</h3>
              <div className="doc-block__body">
                <p>Optionally stop trading after the profit target is reached. Minimum trading-day requirements are tracked so the engine never acts against program rules.</p>
              </div>
            </div>
            <div className="callout callout--warning">
              <span className="callout__title">Programs differ</span>
              Funded programs enforce different limits and definitions. Always read your program agreement and set limits conservatively — your program's rules are the final authority.
            </div>
          </div>
        </div>
      </section>

      <section className="section docs-section" id="ea-settings" aria-labelledby="ea-settings-title">
        <div className="container">
          <SectionHeading
            eyebrow="Guide 05"
            title="EA settings explained"
            description="The input groups you configure on the chart."
          />
          <h2 className="sr-only" id="ea-settings-title">EA settings</h2>
          <div className="docs-section__body">
            <div className="doc-block">
              <h3 className="doc-block__title">Trading inputs</h3>
              <div className="doc-block__body">
                <ul>
                  <li><strong>Risk per trade:</strong> fixed fraction or fixed lots applied to every position.</li>
                  <li><strong>Hard stop loss:</strong> enforced on every trade in account currency or points.</li>
                  <li><strong>Session window:</strong> restrict trading to specific hours and sessions.</li>
                </ul>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">Filter inputs</h3>
              <div className="doc-block__body">
                <ul>
                  <li><strong>News filter:</strong> pause window before and after high-impact events.</li>
                  <li><strong>Spread filter:</strong> maximum live spread allowed for an entry.</li>
                  <li><strong>Structure requirements:</strong> which ICT/SMC elements must confirm before entry.</li>
                </ul>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">Risk and compliance inputs</h3>
              <div className="doc-block__body">
                <ul>
                  <li><strong>Daily loss limit</strong> and <strong>maximum drawdown</strong> in account currency or percent.</li>
                  <li><strong>Profit target:</strong> stop trading once reached, when enabled.</li>
                  <li><strong>Trading days:</strong> minimum days required by your program.</li>
                  <li><strong>Breakeven and trail:</strong> management thresholds for open positions.</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section docs-section" id="support" aria-labelledby="support-title">
        <div className="container">
          <SectionHeading
            eyebrow="Guide 06"
            title="Support and FAQ"
            description="When something is unclear, these are the fastest routes to an answer."
          />
          <h2 className="sr-only" id="support-title">Support and FAQ</h2>
          <div className="docs-section__body">
            <div className="doc-block">
              <h3 className="doc-block__title">Common questions</h3>
              <div className="doc-block__body">
                <p>
                  Activation issues, platform differences, funded-rule behavior, and refunds are
                  covered in the <Link href="/faq">FAQ</Link>. For program-specific setups, read
                  your program agreement first.
                </p>
              </div>
            </div>
            <div className="doc-block">
              <h3 className="doc-block__title">Contact support</h3>
              <div className="doc-block__body">
                <p>
                  Reach the team by email or Telegram from the <Link href="/contact">contact page</Link>.
                  Include your account identifier and a short description so we can help faster.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <CTASection
        title="Your rules are set. Your account is verified."
        description="Create your account and follow the setup order above — the engine will handle the rest with discipline."
      />
    </>
  );
}
