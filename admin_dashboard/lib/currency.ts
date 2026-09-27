const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "€",
  MAD: "MAD",
  GBP: "£",
};

export function formatPrice(amount: number | null | undefined, currency?: string | null): string {
  if (amount == null) return "—";
  const cur = (currency || "USD").toUpperCase();
  const sym = CURRENCY_SYMBOLS[cur] || cur + " ";
  const isMAD = cur === "MAD";
  const formatted = isMAD
    ? amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return isMAD ? `${formatted} ${cur}` : `${sym}${formatted}`;
}
