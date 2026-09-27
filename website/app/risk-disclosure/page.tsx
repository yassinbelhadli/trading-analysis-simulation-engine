import type { Metadata } from "next";
import LegalPage from "@/components/content/LegalPage";
import RiskDisclaimer from "@/components/content/RiskDisclaimer";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Risk Disclosure",
  description:
    "Trading risk disclosure for ICT Funded EA Pro — capital protection emphasis, no guaranteed profits, leveraged product risk, and funded-program rules.",
};

export default function RiskDisclosurePage() {
  return (
    <LegalPage eyebrow="Risk disclosure" title="Trading Risk Disclosure" updated="August 13, 2026">
      <RiskDisclaimer tone="danger" />

      <h2>1. Leveraged products carry substantial risk</h2>
      <p>
        Foreign exchange (FX) and contracts for difference (CFDs) are leveraged products traded on
        margin. Small market movements can produce losses equal to or greater than your deposit.
        Losses can exceed the funds you hold on deposit with your broker, and you can lose all of
        the capital you allocate to trading.
      </p>

      <h2>2. No guaranteed profits</h2>
      <p>
        ICT Funded EA Pro does not and cannot guarantee profits. No software, strategy, or signal
        provider can predict market movements. Any description of the engine, its filters, or
        historical or simulated results is not a promise of future performance. Past or simulated
        performance is not a reliable indicator of future results.
      </p>

      <h2>3. The role of the software</h2>
      <p>
        ICT Funded EA Pro is a tool that follows the rules you configure. It is designed to help
        you enforce risk limits, but:
      </p>
      <ul>
        <li>It cannot prevent losses that occur within your configured limits.</li>
        <li>It cannot prevent slippage, gaps, or requotes during volatile markets.</li>
        <li>It depends on correct installation, configuration, and continuous terminal and network availability.</li>
        <li>It is not a substitute for understanding how trading and your funded program work.</li>
      </ul>

      <h2>4. Capital protection has priority</h2>
      <p>
        The product is engineered around capital protection: daily loss limits, maximum drawdown,
        profit-target tracking, hard stops, and automated pauses around high-impact news. These
        protections only work if you set them to match your risk tolerance and your funded
        program's rules. They do not eliminate risk.
      </p>

      <h2>5. Funded-account programs</h2>
      <p>
        Funded programs have their own rules, including maximum daily loss, maximum drawdown,
        profit targets, minimum trading days, and strategy restrictions. These programs may also
        restrict automated trading. You are solely responsible for reading, understanding, and
        complying with your program's agreement. A breach can result in account termination,
        forfeiture of fees, or loss of the account — regardless of the software you use.
      </p>

      <h2>6. You trade at your own risk</h2>
      <p>
        All decisions to trade, including whether to use ICT Funded EA Pro and how to configure it,
        are yours. ICT Funded EA Pro provides no investment advice and makes no recommendations.
        Only trade with capital you can afford to lose.
      </p>

      <h2>7. Not tax or legal advice</h2>
      <p>
        Nothing on this site or in the Service constitutes tax, legal, or investment advice.
        Consult a qualified professional for guidance specific to your situation and jurisdiction.
      </p>

      <h2>8. Compatibility with your broker</h2>
      <p>
        Confirm with your broker that expert advisors are permitted on your account type and that
        your account meets minimum requirements before use. Some brokers restrict automated
        trading on certain account types or regions.
      </p>

      <h2>9. Acceptance</h2>
      <p>
        By creating an account or activating the software, you confirm that you have read this
        disclosure, understand the risks, and accept that trading outcomes are your sole
        responsibility. If you do not accept these risks, do not use the Service. You can review
        our <Link href="/terms">Terms of Service</Link> and{" "}
        <Link href="/privacy">Privacy Policy</Link> at any time.
      </p>
    </LegalPage>
  );
}
