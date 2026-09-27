import type { Metadata } from "next";
import LegalPage from "@/components/content/LegalPage";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Privacy policy for ICT Funded EA Pro.",
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="August 13, 2026">
      <p>
        This Privacy Policy explains what information ICT Funded EA Pro collects, how it is used,
        and the choices you have. By using the Service you agree to the practices described here.
      </p>

      <h2>1. Information we collect</h2>
      <ul>
        <li>
          <strong>Account information:</strong> name, email address, payment details processed by
          our payment provider, and login credentials (stored securely, never in plain text).
        </li>
        <li>
          <strong>Service information:</strong> license status, linked trading accounts, EA
          configuration, and notification preferences.
        </li>
        <li>
          <strong>Technical information:</strong> terminal and platform version, device and browser
          information, IP address, and logs needed to operate and secure the Service.
        </li>
      </ul>

      <h2>2. How we use information</h2>
      <ul>
        <li>To provide, operate, and improve the Service.</li>
        <li>To validate licenses and prevent unauthorized use.</li>
        <li>To process payments and manage subscriptions.</li>
        <li>To send operational notifications, including rule warnings and risk stops.</li>
        <li>To provide support and respond to your requests.</li>
        <li>To comply with legal obligations.</li>
      </ul>

      <h2>3. Sensitive trading information</h2>
      <p>
        Sensitive account information, including broker connection details and trading-account
        identifiers, is encrypted before storage. Access is restricted to personnel who need it
        to operate the Service. We never log passwords, API keys, or license keys in plain text,
        and we never store your broker password.
      </p>

      <h2>4. Sharing of information</h2>
      <p>
        We do not sell your personal information. We share information only with trusted service
        providers (hosting, payments, analytics) that are bound by confidentiality obligations, or
        when required by law, or to protect the rights and safety of users and the Service.
      </p>

      <h2>5. Data retention</h2>
      <p>
        We retain account and service data while your account is active and for a reasonable period
        afterward to comply with legal and accounting requirements. We never delete client trading
        data automatically without a lawful basis.
      </p>

      <h2>6. Cookies and analytics</h2>
      <p>
        The Service uses strictly necessary cookies and, where permitted, privacy-respecting
        analytics to understand usage. You can disable cookies in your browser; core functionality
        will continue to work.
      </p>

      <h2>7. Your rights</h2>
      <p>
        Depending on your jurisdiction, you may have the right to access, correct, export, or
        delete your personal information, and to object to or restrict certain processing. To
        exercise these rights, contact us through the <Link href="/contact">contact page</Link>.
      </p>

      <h2>8. Security</h2>
      <p>
        We apply encryption, access controls, and monitoring to protect your information. No method
        of transmission or storage is completely secure, so we cannot guarantee absolute security.
        You are responsible for keeping your own credentials safe.
      </p>

      <h2>9. Children</h2>
      <p>
        The Service is not directed to individuals under 18 years of age. We do not knowingly
        collect personal information from children.
      </p>

      <h2>10. Changes to this policy</h2>
      <p>
        We may update this Privacy Policy from time to time. Material changes will be announced
        through the Service, and the updated policy will show a new effective date.
      </p>

      <h2>11. Contact</h2>
      <p>
        Privacy questions can be sent through the <Link href="/contact">contact page</Link>.
      </p>
    </LegalPage>
  );
}
