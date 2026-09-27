import Link from "next/link";
import { footerGroups } from "@/lib/navigation";
import { portalUrls } from "@/lib/urls";
import Logo from "@/components/primitives/Logo";

export default function WebsiteFooter() {
  return (
    <footer className="website-footer">
      <div className="container">
        <div className="website-footer__grid">
          <div>
            <Logo />
            <p className="website-footer__tagline">
              Disciplined algorithmic trading for funded-account traders. Market-structure
              execution, funded-rule compliance, and capital protection on MetaTrader 4 and 5.
            </p>
          </div>
          {footerGroups.map((group) => (
            <div key={group.title}>
              <h2 className="website-footer__title">{group.title}</h2>
              {group.links.map((link) => (
                <Link className="website-footer__link" key={link.href} href={link.href}>{link.label}</Link>
              ))}
            </div>
          ))}
          <div>
            <h2 className="website-footer__title">Portal</h2>
            <a className="website-footer__link" href={portalUrls.clientLogin}>Client login</a>
            <a className="website-footer__link" href={portalUrls.clientRegister}>Create account</a>
          </div>
        </div>
        <div className="website-footer__meta">
          <span>© {new Date().getFullYear()} ICT Funded EA Pro. All rights reserved.</span>
          <span>Not investment advice. Trading leveraged products carries risk.</span>
        </div>
      </div>
    </footer>
  );
}
