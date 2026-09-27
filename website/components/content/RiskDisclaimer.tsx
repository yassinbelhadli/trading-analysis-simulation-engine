type RiskDisclaimerProps = {
  tone?: "warning" | "danger";
  className?: string;
};

export default function RiskDisclaimer({ tone = "warning", className = "" }: RiskDisclaimerProps) {
  const classes = ["risk-note", tone === "danger" ? "risk-note--danger" : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <aside className={classes}>
      <strong>Trading involves risk.</strong>{" "}
      Trading foreign exchange and CFDs on margin carries a high level of risk and is not suitable
      for all investors. ICT Funded EA Pro is a tool that follows your configured rules; it does not
      guarantee profits, it cannot prevent every loss, and past or simulated performance is not a
      reliable indicator of future results. Never risk more than you can afford to lose.
    </aside>
  );
}
