/**
 * Currency formatting utility — no currency conversion.
 * All prices come from the backend with explicit per-currency values.
 */

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "€",
  MAD: "MAD",
};

/**
 * Format an amount with its currency code.
 * - USD → "$12.00"
 * - EUR → "€10.00"
 * - MAD → "100.00 MAD"
 */
export function formatPrice(amount: number | null | undefined, currency: string = "USD"): string {
  if (amount == null) return "—";
  const num = Number(amount);
  if (isNaN(num)) return "—";

  const code = (currency || "USD").toUpperCase();
  const symbol = CURRENCY_SYMBOLS[code] || code;

  if (code === "MAD") {
    // MAD: amount first, then code (e.g. "100.00 MAD")
    return `${num.toFixed(2)} ${symbol}`;
  }
  // USD/EUR: symbol first (e.g. "$12.00", "€10.00")
  return `${symbol}${num.toFixed(2)}`;
}

/**
 * Get the price for a given currency from a plan's multi-currency fields.
 */
export function getPlanPrice(
  plan: { price_usd?: number | null; price_eur?: number | null; price_mad?: number | null },
  currency: string = "USD",
): number | null {
  const code = (currency || "USD").toUpperCase();
  switch (code) {
    case "EUR": return plan.price_eur ?? null;
    case "MAD": return plan.price_mad ?? null;
    default: return plan.price_usd ?? null;
  }
}
