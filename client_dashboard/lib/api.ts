import { authFetch } from "./auth";

/** Map internal payment method IDs to display names */
export const PAYMENT_METHOD_LABELS: Record<string, string> = {
  stripe: "Stripe",
  ci_bank: "CIH Bank / Card",
  cmi: "CMI",
  payzone: "Payzone",
  binance_pay: "Binance Pay",
  apple_pay: "Apple Pay",
  google_pay: "Google Pay",
  cash_plus: "Cash Plus",
  wafa_cash: "Wafa Cash",
  btc: "Bitcoin",
  eth: "Ethereum",
  sol: "Solana",
  usdt: "USDT (Tether)",
};

/** Get display label for a payment method ID */
export function getPaymentMethodLabel(method: string | null | undefined): string {
  if (!method) return "—";
  return PAYMENT_METHOD_LABELS[method] || method;
}

export interface DashboardLicense {
  status: string | null;
  plan: string | null;
  expires_at: string | null;
  days_remaining: number | null;
  max_accounts: number;
  used_accounts: number;
}

export interface DashboardSubscription {
  plan: string | null;
  active: boolean;
  billing_cycle: string | null;
  renew_date: string | null;
  days_remaining: number | null;
}

export interface TradingStatus {
  running: boolean;
  mt5_connected: boolean;
  telegram_connected: boolean;
  accounts_count: number;
}

export interface DashboardSignal {
  id: string;
  symbol: string;
  direction: string;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  created_at: string | null;
}

export interface DashboardTrade {
  id: string;
  symbol: string;
  direction: string;
  status: string;
  lot_size: number | null;
  realized_pnl: number | null;
  realized_r: number | null;
  close_reason: string | null;
  closed_at: string | null;
}

export interface EquityPoint {
  date: string | null;
  equity: number;
}

export interface ClientDashboardResponse {
  welcome_name: string;
  license: DashboardLicense | null;
  subscription: DashboardSubscription | null;
  trading_status: TradingStatus;
  today: { profit: number; win_rate: number; open_trades: number; closed_trades: number };
  totals: { balance: number; equity: number; total_pnl: number; total_trades: number; profit_factor: number };
  recent_signals: DashboardSignal[];
  recent_trades: DashboardTrade[];
  equity_curve: EquityPoint[];
}

export interface ClientProfile {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  avatar: string | null;
  country: string | null;
  language: string;
  timezone: string | null;
  email_verified: boolean;
  telegram_id: number | null;
  telegram_username: string | null;
  created_at: string | null;
}

export interface ClientLicense {
  id: string;
  license_key: string;
  plan: string;
  status: string;
  max_accounts: number;
  used_accounts: number;
  bound_account_id: string | null;
  bound_at: string | null;
  transfer_locked: boolean;
  created_at: string | null;
  expires_at: string | null;
  days_remaining: number | null;
}

export interface LicenseHistoryEntry {
  event_type: string;
  message: string;
  details: Record<string, unknown> | null;
  created_at: string | null;
}

export interface ClientLicenseResponse {
  items: ClientLicense[];
  total: number;
  activation_history: LicenseHistoryEntry[];
}

export interface SubscriptionInvoice {
  id: string;
  event_type: string;
  message: string;
  amount: number | null;
  currency: string;
  method: string | null;
  status: string;
  created_at: string | null;
}

export interface AvailablePlan {
  id: string;
  name: string;
  price_monthly: number | null;
  price_yearly: number | null;
  one_time_price: number | null;
  max_accounts: number;
  on_sale: boolean;
  old_price: number | null;
  // Multi-currency fields (from PlanDefinition)
  price_usd: number | null;
  price_eur: number | null;
  price_mad: number | null;
  duration_days: number | null;
  features_json: string | null;
  description: string | null;
  badge: string | null;
  display_order: number;
}

export interface ClientSubscriptionResponse {
  subscription: {
    plan: string;
    plan_name: string;
    active: boolean;
    price: number | null;
    billing_cycle: string | null;
    start_date: string | null;
    renew_date: string | null;
    days_remaining: number | null;
    plan_currency: string | null;
  } | null;
  payment_method: string | null;
  invoices: SubscriptionInvoice[];
  available_plans: AvailablePlan[];
}

export interface ClientAccount {
  id: string;
  name: string;
  platform: string;
  server: string | null;
  login: string | null;
  broker: string;
  account_type: string;
  engine_status: string;
  active: boolean;
  verified: boolean;
  balance: number | null;
  equity: number | null;
  currency: string;
  leverage: string | null;
  demo_real: string | null;
  account_size: number | null;
  license_id: string | null;
  connected: boolean;
  last_sync: string | null;
  created_at: string | null;
}

export interface AccountLimits {
  used: number;
  max: number;
  unlimited: boolean;
}

export interface ClientAccountsResponse {
  items: ClientAccount[];
  total: number;
  limits: AccountLimits;
}

export interface TelegramStatus {
  connected: boolean;
  bot_username: string;
  bot_id: number;
  chat_id: number | null;
  telegram_username: string | null;
  language: string;
  bot_link: string;
  notifications: Record<string, boolean>;
}

export interface TelegramLoginResponse {
  url: string;
}

export interface TelegramCallbackResponse {
  success: boolean;
  telegram_id?: number;
  telegram_username?: string | null;
  detail?: string;
}

export interface TelegramAuthorizeResponse {
  message: string;
  connected: boolean;
  telegram_id: number;
  telegram_username: string | null;
}

export interface EABuildInfo {
  id: string;
  version: string;
  release_notes: string | null;
  changelog: string | null;
  released_at: string | null;
  windows_available: boolean;
  macos_available: boolean;
}

export interface ClientSettings {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  language: string;
  timezone: string | null;
  email_verified: boolean;
  telegram_id: number | null;
  telegram_username: string | null;
  billing_currency: string | null;
  preferences: {
    theme: string;
    news_alerts_enabled: boolean;
    email_notifications: boolean;
    telegram_notifications: boolean;
    notifications: Record<string, boolean>;
  };
}

export interface ClientTrade {
  id: string;
  symbol: string;
  direction: string;
  status: string;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  lot_size: number | null;
  realized_pnl: number | null;
  realized_r: number | null;
  close_reason: string | null;
  created_at: string | null;
  closed_at: string | null;
  partial_closed: boolean;
  breakeven_activated: boolean;
}

export interface PerformanceData {
  total_trades: number;
  net_pnl: number;
  profit_factor: number;
  win_rate: number;
  avg_r: number;
  max_drawdown: number;
  by_symbol: { symbol: string; trades: number; pnl: number; wins: number; losses: number }[];
  by_month: { month: string; trades: number; pnl: number }[];
  equity_curve: { date: string; equity: number }[];
}

// ---------------------------------------------------------------------------
// Dashboard / overview
// ---------------------------------------------------------------------------
export const getClientDashboard = () => authFetch<ClientDashboardResponse>("/api/client/dashboard");
export const getClientProfile = () => authFetch<ClientProfile>("/api/client/profile");
export const updateClientProfile = (data: Record<string, unknown>) =>
  authFetch<{ message: string; profile: ClientProfile }>("/api/client/profile", {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// ---------------------------------------------------------------------------
// License / subscription
// ---------------------------------------------------------------------------
export const getMyLicense = () => authFetch<ClientLicenseResponse>("/api/client/license");
export const getMySubscription = () => authFetch<ClientSubscriptionResponse>("/api/client/subscription");
export const getSubscriptionHistory = () =>
  authFetch<{ subscriptions: Array<{
    id: string; subscription_number: string; plan: string; plan_name: string;
    plan_currency: string | null; plan_price_paid: number | null;
    active: boolean; billing_cycle: string | null;
    coupon_code: string | null; discount_amount: number | null;
    start_date: string | null; end_date: string | null;
    days_remaining: number; created_at: string | null;
  }> }>("/api/client/subscription/history");
export const cancelSubscription = () => authFetch<{ message: string }>("/api/client/subscription/cancel", { method: "POST" });
export const renewSubscription = () =>
  authFetch<{ message: string; renew_date: string }>("/api/client/subscription/renew", { method: "POST" });
export const listAvailablePlans = () => authFetch<{ plans: AvailablePlan[] }>("/api/client/plans");
export const subscribeToPlan = (data: { plan_id: string; currency?: string; coupon_code?: string }) =>
  authFetch<{ success: boolean; subscription: any; coupon?: any }>("/api/client/subscription", {
    method: "POST",
    body: JSON.stringify(data),
  });

// ---------------------------------------------------------------------------
// Coupons (client-side validation)
// ---------------------------------------------------------------------------
export const clientValidateCoupon = (data: { code: string; plan_id: string; currency: string }) =>
  authFetch<{ valid: boolean; coupon_code: string; original_price: number; discount_amount: number; final_price: number; message: string }>("/api/client/coupons/validate", {
    method: "POST",
    body: JSON.stringify(data),
  });

// ---------------------------------------------------------------------------
// Billing currency
// ---------------------------------------------------------------------------
export const getClientBillingCurrency = () => authFetch<{ billing_currency: string }>("/api/client/settings");
export const updateClientBillingCurrency = (currency: string) =>
  authFetch<{ message: string; updated: string[]; preferences: Record<string, unknown> }>("/api/client/settings", {
    method: "PATCH",
    body: JSON.stringify({ billing_currency: currency }),
  });

// ---------------------------------------------------------------------------
// Trades / performance
// ---------------------------------------------------------------------------
export const getClientTrades = (params?: string) =>
  authFetch<{ items: ClientTrade[]; total: number }>(`/api/client/trades${params || ""}`);
export const getClientPerformance = () => authFetch<PerformanceData>("/api/client/performance");

// ---------------------------------------------------------------------------
// Account Risk Profile
// ---------------------------------------------------------------------------
export interface RiskStatus {
  account_id: string;
  account_type: string;
  risk_level: "SAFE" | "REDUCED" | "BLOCKED" | "UNVERIFIED" | "UNKNOWN";
  risk_level_message: string;
  balance: number;
  equity: number;
  currency: string;
  floating_pnl: number;
  today_realized_pnl: number;
  today_floating_pnl: number;
  initial_balance: number;
  high_water_mark: number;
  current_drawdown_pct: number;
  current_drawdown_usd: number;
  drawdown_type: string;
  daily_loss_limit_pct: number;
  daily_loss_limit_usd: number;
  current_daily_loss_usd: number;
  remaining_daily_loss_usd: number;
  remaining_daily_loss_pct: number;
  max_loss_limit_pct: number;
  max_loss_limit_usd: number;
  total_realized_loss_usd: number;
  remaining_max_loss_usd: number;
  remaining_max_loss_pct: number;
  open_positions_count: number;
  total_open_risk_usd: number;
  safety_buffer_pct: number;
  safety_buffer_usd: number;
  proposed_trade_risk_usd: number;
  projected_risk_after_trade_usd: number;
  distance_to_daily_violation_usd: number;
  distance_to_max_violation_usd: number;
  prop_firm: string | null;
  prop_firm_program: string | null;
  verification_status: string;
  trading_mode: string;
  last_scan_at: string | null;
  last_risk_update: string | null;
  data_freshness: string;
  risk_profile_missing: boolean;
  balance_stale: boolean;
  risk_calculation_failed: boolean;
}

export const getAccountRisk = (accountId: string) =>
  authFetch<RiskStatus>(`/api/client/accounts/${accountId}/risk`);

// ---------------------------------------------------------------------------
// Trading Mode (per-account)
// ---------------------------------------------------------------------------
export const getAccountTradingMode = (accountId: string) =>
  authFetch<{ account_id: string; trading_mode: string }>(`/api/client/accounts/${accountId}/trading-mode`);

export const updateAccountTradingMode = (accountId: string, trading_mode: string) =>
  authFetch<{ message: string; trading_mode: string }>(`/api/client/accounts/${accountId}/trading-mode`, {
    method: "PATCH",
    body: JSON.stringify({ trading_mode }),
  });

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
export const getClientSettings = () => authFetch<ClientSettings>("/api/client/settings");
export const updateClientSettings = (data: Record<string, unknown>) =>
  authFetch<{ message: string; updated: string[]; preferences: Record<string, unknown> }>("/api/client/settings", {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// ---------------------------------------------------------------------------
// MT5 accounts
// ---------------------------------------------------------------------------
export const listClientAccounts = () => authFetch<ClientAccountsResponse>("/api/client/accounts");
export const addClientAccount = (data: Record<string, unknown>) =>
  authFetch<{ message: string; account: ClientAccount }>("/api/client/accounts", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const renameClientAccount = (accountId: string, name: string) =>
  authFetch<{ message: string; account: ClientAccount }>(`/api/client/accounts/${accountId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
export const deleteClientAccount = (accountId: string) =>
  authFetch<{ message: string }>(`/api/client/accounts/${accountId}`, { method: "DELETE" });
export const disconnectClientAccount = (accountId: string) =>
  authFetch<{ message: string; account: ClientAccount }>(`/api/client/accounts/${accountId}/disconnect`, { method: "POST" });
export const reconnectClientAccount = (accountId: string, password?: string) =>
  authFetch<{ message: string; account: ClientAccount }>(`/api/client/accounts/${accountId}/reconnect`, {
    method: "POST",
    body: JSON.stringify({ password: password || "" }),
  });

// ---------------------------------------------------------------------------
// Telegram — OIDC Authorization Code + PKCE flow
// ---------------------------------------------------------------------------
export const getTelegramStatus = () => authFetch<TelegramStatus>("/api/client/telegram");
export const getTelegramLoginUrl = () => authFetch<TelegramLoginResponse>("/api/client/telegram/login");
export const disconnectTelegram = () =>
  authFetch<{ message: string; connected: boolean }>("/api/client/telegram/disconnect", { method: "POST" });
export const updateTelegramPreferences = (data: {
  notifications?: Record<string, boolean>;
  language?: string;
}) =>
  authFetch<{ message: string; notifications: Record<string, boolean>; language: string }>(
    "/api/client/telegram/preferences",
    { method: "PATCH", body: JSON.stringify(data) },
  );
export const testTelegram = () =>
  authFetch<{ message: string; chat_id: number }>("/api/client/telegram/test", { method: "POST" });

// ---------------------------------------------------------------------------
// EA downloads
// ---------------------------------------------------------------------------
export const getEABuilds = () =>
  authFetch<{ latest: EABuildInfo | null; changelog: EABuildInfo[]; total: number }>("/api/client/ea");
export const checkEAUpdates = (current_version: string) =>
  authFetch<{ update_available: boolean; current_version: string | null; latest_version: string | null }>(
    "/api/client/ea/check-updates",
    { method: "POST", body: JSON.stringify({ current_version }) },
  );
export const downloadEABuild = (buildId: string) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("client_at") : null;
  return fetch(`/_api/api/client/ea/download/${buildId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
};

// ---------------------------------------------------------------------------
// Support tickets (shared backend records)
// ---------------------------------------------------------------------------
export interface TicketMessage {
  id: string;
  author_user_id: string | null;
  author_role: string;
  author_name: string | null;
  kind: string;
  is_internal: boolean;
  body: string;
  created_at: string | null;
}

export interface ClientTicket {
  id: string;
  ticket_number: string;
  subject: string;
  description: string;
  category: string;
  status: string;
  priority: string;
  escalated: boolean;
  escalated_at: string | null;
  source: string;
  created_at: string | null;
  updated_at: string | null;
  closed_at: string | null;
  resolved_at: string | null;
  messages: TicketMessage[];
}

export const TICKET_CATEGORIES = [
  "connection",
  "license",
  "performance",
  "billing",
  "account",
  "bug",
  "other",
] as const;

export const TICKET_STATUSES = ["open", "in_progress", "resolved", "closed"] as const;

export const listMyTickets = (params?: string) =>
  authFetch<{ tickets: ClientTicket[]; total: number; page: number; limit: number }>(
    `/api/client/support${params || ""}`,
  );
export const getMyTicket = (ticketId: string) =>
  authFetch<{ ticket: ClientTicket }>(`/api/client/support/${ticketId}`);
export const createMyTicket = (data: {
  subject: string;
  description: string;
  category: string;
  priority?: string;
}) =>
  authFetch<{ ticket: ClientTicket; message: string }>("/api/client/support", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const replyToMyTicket = (ticketId: string, message: string) =>
  authFetch<{ message: string; ticket: ClientTicket }>(`/api/client/support/${ticketId}/reply`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });

// --- Economic calendar (news pipeline, canonical source: DB news_events) ---
export interface CalendarEvent {
  news_id: string;
  time: string | null;
  currency: string;
  event: string;
  impact: string;
  actual: string | null;
  forecast: string | null;
  previous: string | null;
  status: string | null;
}

export interface CalendarResponse {
  items: CalendarEvent[];
  total: number;
  window_days: number;
}

export interface RecentNewsResponse {
  items: CalendarEvent[];
  total: number;
  window_hours: number;
}

export const getUpcomingCalendar = (days = 7, impact = "HIGH,MEDIUM") =>
  authFetch<CalendarResponse>(
    `/api/client/news?days=${days}&impact=${encodeURIComponent(impact)}`,
  );

export const getRecentNews = (hours = 48) =>
  authFetch<RecentNewsResponse>(`/api/client/news/recent?hours=${hours}`);

// ---------------------------------------------------------------------------
// Payment types + functions
// ---------------------------------------------------------------------------

export interface PaymentInfo {
  id: string;
  payment_number: string;
  user_id: string;
  subscription_id: string | null;
  plan_id: string;
  plan_name: string | null;
  plan_duration_days: number | null;
  original_amount: number;
  discount_amount: number;
  final_amount: number;
  currency: string;
  coupon_code: string | null;
  payment_provider: string;
  payment_method_type: string | null;
  provider_payment_id: string | null;
  payment_method: string | null;
  status: string;
  failure_reason: string | null;
  // Manual payment fields
  manual_reference: string | null;
  manual_proof_url: string | null;
  manual_instructions: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  internal_notes: string | null;
  // Timestamps
  created_at: string | null;
  paid_at: string | null;
  failed_at: string | null;
  refunded_at: string | null;
}

export interface ReceiptInfo {
  id: string;
  receipt_number: string;
  payment_id: string;
  plan_name: string;
  plan_duration_days: number | null;
  original_amount: number;
  discount_amount: number;
  final_amount: number;
  currency: string;
  coupon_code: string | null;
  payment_method: string | null;
  payment_status: string;
  paid_at: string | null;
  subscription_start: string | null;
  subscription_expiration: string | null;
  created_at: string | null;
}

export interface CheckoutSession {
  payment_id: string;
  payment_number: string;
  checkout_url: string;
  checkout_id: string;
  subscription_id: string;
  subscription_number: string;
  status: string;
  payment_method_type: string | null;
  manual_instructions: string | null;
  manual_reference: string | null;
  deposit_address: string | null;
  network: string | null;
  ticker: string | null;
  expected_amount: string | null;
  expired_at: string | null;
  confirmations_required: number | null;
  reference_required?: boolean | null;
  owner_config?: PaymentMethodConfig | null;
}

export interface ClientFieldDef {
  key: string;
  label: string;
  type: string;
  required: boolean;
  placeholder?: string | null;
  validation?: string | null;
}

export interface InfoBlock {
  label: string;
  value: string;
}

export interface PaymentMethodConfig {
  id: string;
  method_id: string;
  method_type: string;
  display_name: string;
  description: string | null;
  information: InfoBlock[] | null;
  client_fields: ClientFieldDef[] | null;
  receipt_required: boolean;
  instructions: string | null;
  reference_instructions: string | null;
  reference_required: boolean;
  wallet_address: string | null;
  network: string | null;
  expires_hours: number;
  is_active: boolean;
  display_order: number;
}

export interface PaymentMethod {
  name: string;
  display_name: string;
  type: string;
  description: string;
  icon: string;
  state: string;
  is_configured: boolean;
  is_manual: boolean;
  category?: string;
  ticker?: string | null;
  config?: PaymentMethodConfig | null;
}

export interface PaymentMethodsResponse {
  currency: string;
  methods: PaymentMethod[];
}

export interface ProviderStatus {
  configured: boolean;
  provider: string;
  providers?: Array<{
    name: string;
    display_name: string;
    type: string;
    state: string;
    is_configured: boolean;
    is_manual: boolean;
    supported_currencies: string[];
  }>;
}

export interface PaymentHistoryResponse {
  payments: PaymentInfo[];
  total: number;
}

export interface CheckoutResponse {
  success: boolean;
  checkout: CheckoutSession;
}

export interface CheckoutStatusResponse {
  payment: PaymentInfo;
  subscription: {
    status: string;
    active: boolean;
    subscription_number: string;
  } | null;
  receipt: ReceiptInfo | null;
}

// Create checkout session (new payment flow)
export const createCheckout = (params: {
  plan_id: string;
  currency: string;
  coupon_code?: string;
  payment_method?: string;
  success_url?: string;
  cancel_url?: string;
}) =>
  authFetch<CheckoutResponse>("/api/client/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

// Check checkout/payment status (poll after redirect)
export const getCheckoutStatus = (paymentId: string) =>
  authFetch<CheckoutStatusResponse>(`/api/client/checkout/status/${paymentId}`);

// Payment history
export const getPaymentHistory = (limit = 50, offset = 0) =>
  authFetch<PaymentHistoryResponse>(`/api/client/payments?limit=${limit}&offset=${offset}`);

// Single payment detail
export const getPaymentDetail = (paymentId: string) =>
  authFetch<{ payment: PaymentInfo }>(`/api/client/payments/${paymentId}`);

// Cancel pending payment
export const cancelPayment = (paymentId: string) =>
  authFetch<{ success: boolean; payment: PaymentInfo }>(
    `/api/client/payments/${paymentId}/cancel`,
    { method: "POST" },
  );

// Submit manual payment reference
export const submitManualPayment = (paymentId: string, data: {
  manual_reference?: string;
  manual_proof_url?: string;
  payer_name?: string;
  payer_phone?: string;
  payment_date?: string;
  amount_paid?: number;
  client_fields_data?: Record<string, unknown>;
}) =>
  authFetch<{ success: boolean; payment: PaymentInfo }>(
    `/api/client/payments/${paymentId}/submit`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) },
  );

// Upload proof-of-payment file (JPG/PNG/PDF, max 10 MB)
export const uploadPaymentProof = (paymentId: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return authFetch<{ success: boolean; url: string; filename: string; size_bytes: number }>(
    `/api/client/payments/${paymentId}/upload-proof`,
    { method: "POST", body: form },
  );
};

// Receipt list
export const getReceipts = (limit = 50, offset = 0) =>
  authFetch<{ receipts: ReceiptInfo[] }>(`/api/client/receipts?limit=${limit}&offset=${offset}`);

// Single receipt detail
export const getReceipt = (receiptNumber: string) =>
  authFetch<{ receipt: ReceiptInfo }>(`/api/client/receipts/${receiptNumber}`);

// Check if payment provider is configured
export const getProviderStatus = () =>
  authFetch<ProviderStatus>("/api/client/provider/status");

// List available payment methods for a currency
export const getPaymentMethods = (currency: string) =>
  authFetch<PaymentMethodsResponse>(`/api/client/payment-methods?currency=${currency}`);
