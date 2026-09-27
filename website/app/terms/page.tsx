import type { Metadata } from "next";
import LegalPage from "@/components/content/LegalPage";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Terms of service for ICT Funded EA Pro software subscriptions.",
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" updated="August 13, 2026">
      <p>
        These Terms of Service ("Terms") govern your use of the ICT Funded EA Pro website,
        client portal, software, and related services (collectively, the "Service"). By creating
        an account or using the Service, you agree to these Terms.
      </p>

      <h2>1. About the Service</h2>
      <p>
        ICT Funded EA Pro is a software product that provides an algorithmic expert advisor (EA)
        for MetaTrader 4 and MetaTrader 5, a client dashboard, and Telegram notifications. The
        Service is intended for traders using funded-account programs that permit automated
        trading. It is a tool, not investment advice.
      </p>

      <h2>2. Accounts and eligibility</h2>
      <p>
        You must be at least 18 years old and legally able to trade in your jurisdiction to use
        the Service. You are responsible for the accuracy of the information you provide and for
        safeguarding your account credentials. You agree to notify us promptly of any unauthorized
        use of your account.
      </p>

      <h2>3. Subscriptions and payments</h2>
      <ul>
        <li>Subscriptions are billed monthly unless a one-time license is purchased.</li>
        <li>Prices are displayed at the time of purchase and may be updated with notice.</li>
        <li>You may cancel at any time; access continues until the end of the paid period.</li>
        <li>Refunds are governed by our refund policy below.</li>
      </ul>

      <h2>4. Licenses</h2>
      <p>
        Your subscription grants you a limited, non-exclusive, non-transferable license to use
        the Service for your own trading accounts, up to the account limit of your plan. You may
        not resell, redistribute, sublicense, decompile, or modify the software. Licenses are
        validated before activation; an expired license disables trading with notice to you.
      </p>

      <h2>5. Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>Use the Service for any unlawful purpose or in a manner that violates your broker's or funded program's rules.</li>
        <li>Attempt to bypass license validation, security controls, or rate limits.</li>
        <li>Share, lease, or resell access, credentials, or license keys.</li>
        <li>Misrepresent the performance or nature of the Service.</li>
      </ul>

      <h2>6. Risk acknowledgment</h2>
      <p>
        Trading foreign exchange and CFDs on margin carries a high level of risk. The Service
        cannot guarantee profits, prevent losses, or ensure compliance with any specific funded
        program. You are solely responsible for configuring the Service correctly and for reading
        and following your funded program's rules. See the{" "}
        <Link href="/risk-disclosure">Risk Disclosure</Link> for details.
      </p>

      <h2>7. No investment advice</h2>
      <p>
        ICT Funded EA Pro does not provide investment, legal, or tax advice. Nothing in the
        Service is a recommendation to buy or sell any financial instrument. Decisions to trade
        are yours alone.
      </p>

      <h2>8. Intellectual property</h2>
      <p>
        All software, documentation, logos, and content provided as part of the Service are the
        property of ICT Funded EA Pro or its licensors and are protected by applicable law. You
        acquire no ownership rights through your use of the Service.
      </p>

      <h2>9. Disclaimers and limitation of liability</h2>
      <p>
        The Service is provided "as is" and "as available" without warranties of any kind, express
        or implied, including fitness for a particular purpose. To the maximum extent permitted by
        law, ICT Funded EA Pro shall not be liable for any indirect, incidental, special,
        consequential, or punitive damages, or for any trading losses, arising from your use of the
        Service.
      </p>

      <h2>10. Refund policy</h2>
      <p>
        New subscriptions qualify for a 14-day refund if the Service does not work as described in
        the documentation. Refund requests must be submitted through support within the refund
        window. One-time licenses and renewal charges are handled on a case-by-case basis.
      </p>

      <h2>11. Termination</h2>
      <p>
        You may stop using the Service at any time. We may suspend or terminate access for
        violation of these Terms, for abusive behavior, or as required by law. Termination does
        not affect your accrued obligations.
      </p>

      <h2>12. Changes to these Terms</h2>
      <p>
        We may update these Terms from time to time. Material changes will be announced through
        the Service. Continued use after changes take effect constitutes acceptance.
      </p>

      <h2>13. Contact</h2>
      <p>
        Questions about these Terms can be sent through the{" "}
        <Link href="/contact">contact page</Link>.
      </p>
    </LegalPage>
  );
}
