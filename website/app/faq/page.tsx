import type { Metadata } from "next";
import CTASection from "@/components/content/CTASection";
import PageHero from "@/components/content/PageHero";
import Icon from "@/components/primitives/Icon";
import Link from "next/link";

export const metadata: Metadata = {
  title: "FAQ",
  description:
    "Answers to common questions about ICT Funded EA Pro: activation, supported platforms, funded-account rules, risk stops, support, refunds, and security.",
};

const faqs = [
  {
    question: "How does the EA decide to enter a trade?",
    answer:
      "Every entry must pass the ICT/SMC pipeline: market structure and bias, liquidity targets, fair value gaps, order blocks, and a confirmation signal. On top of that, the risk engine checks funded-rule limits, spread, and news status before an order is placed.",
  },
  {
    question: "Which platforms are supported?",
    answer:
      "Both MetaTrader 4 and MetaTrader 5 are fully supported. The EA detects the platform automatically on first load, so the same license and the same engine work on either terminal.",
  },
  {
    question: "Will the EA work with my funded program's rules?",
    answer:
      "The EA is designed for funded programs that allow MT4/MT5 expert advisors. Daily loss, maximum drawdown, profit target, and minimum trading days are all configurable, but you must confirm your program's exact rules and set the limits accordingly before activation.",
  },
  {
    question: "What happens if a funded rule is about to be breached?",
    answer:
      "The risk engine monitors balance, equity, and open exposure continuously. When a limit is approached, the EA stops opening new trades and can close risk positions based on your settings. You are notified immediately, and capital protection always takes priority.",
  },
  {
    question: "Does the EA trade during high-impact news?",
    answer:
      "No. The news filter pauses trading automatically around high-impact economic releases using a configurable window before and after each event. Trading resumes according to your settings.",
  },
  {
    question: "How is my license activated?",
    answer:
      "After registration you receive a license key in the client portal. The EA validates the license before the bot activates. If a license expires, trading is disabled and you are notified — activation never happens without a valid license.",
  },
  {
    question: "Can I run multiple funded accounts?",
    answer:
      "Yes. The Professional plan covers up to three accounts and the Premium plan up to ten, each with its own rule set and limits. The Starter plan covers a single account; Enterprise supports unlimited accounts.",
  },
  {
    question: "What support is included?",
    answer:
      "All plans include email support through the client portal. Premium and Enterprise include priority support, and Enterprise includes dedicated onboarding and 24/7 support. You can also reach us directly via our contact page.",
  },
  {
    question: "Do you offer refunds?",
    answer:
      "We offer a 14-day refund period on new subscriptions if the product does not work as described in the documentation. Setup fees and one-time licenses are handled on a case-by-case basis — contact support within the refund window for assistance.",
  },
  {
    question: "Is trading with the EA risk-free?",
    answer:
      "No. Trading leveraged products carries substantial risk and is not suitable for all investors. The EA follows your configured rules and cannot guarantee profits or prevent every loss. Only trade with capital you can afford to lose, and read the full risk disclosure.",
  },
];

export default function FaqPage() {
  return (
    <>
      <PageHero
        eyebrow="FAQ"
        title="Questions, answered."
        description="Everything you need to know about activation, platforms, funded rules, risk stops, support, refunds, and security."
        align="center"
      />

      <section className="section" aria-labelledby="faq-list-title">
        <div className="container">
          <h2 className="sr-only" id="faq-list-title">Frequently asked questions</h2>
          <div className="faq-list">
            {faqs.map((faq) => (
              <details className="faq-item" key={faq.question}>
                <summary className="faq-item__summary">
                  {faq.question}
                  <Icon className="faq-item__icon" name="plus" size={20} />
                </summary>
                <div className="faq-item__content">
                  <p>{faq.answer}</p>
                </div>
              </details>
            ))}
          </div>
          <p className="pricing-note">
            Still have a question? Read the <Link href="/docs">documentation</Link> or{" "}
            <Link href="/contact">contact support</Link>.
          </p>
        </div>
      </section>

      <CTASection
        title="Have your own setup to protect?"
        description="Register, link your MetaTrader account, and configure your funded rules before the engine starts trading."
      />
    </>
  );
}
