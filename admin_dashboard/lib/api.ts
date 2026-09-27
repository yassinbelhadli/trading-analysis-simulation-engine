import { getAccessToken, refreshAccessToken } from "./auth";

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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// ---------------------------------------------------------------------------
// Authenticated fetch (auto-refresh on 401)
// ---------------------------------------------------------------------------
export async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const doFetch = (tok: string | null) => {
    const h: Record<string, string> = { ...headers };
    if (tok) h["Authorization"] = `Bearer ${tok}`;
    return fetch(`${API_BASE}${path}`, { ...init, headers: { ...h, ...init?.headers } });
  };

  let res = await doFetch(token);

  // Attempt token refresh on 401
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      token = newToken;
      res = await doFetch(token);
    }
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface OverviewEngine {
  pid: number | null;
  instance_id: string | null;
  started_at: string | null;
  uptime_hours: number | null;
  status: string;
  cycles: number | null;
  mt5_connected: boolean;
  telegram_connected: boolean;
  heartbeat_age_sec: number | null;
  memory_mb: number | null;
  cpu_percent: number | null;
  active_trades: number;
}

export interface OverviewCounts {
  total_clients: number;
  active_subscriptions: number;
  connected_accounts: number;
  open_support_tickets: number;
}

export interface OverviewResponse {
  engine: OverviewEngine;
  counts: OverviewCounts;
  errors_24h: number;
}

export interface UserItem {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  telegram_username: string | null;
  role: string | null;
  account_status: string;
  email_verified: boolean;
  language: string;
  created_at: string | null;
  last_login: string | null;
  licenses_count: number;
  accounts_count: number;
}

export interface PaginatedUsers {
  items: UserItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface RoleItem {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: { id: string; resource: string; action: string }[];
}

export interface PermissionItem {
  id: string;
  resource: string;
  action: string;
  description: string | null;
}

export interface AuditLogItem {
  id: string;
  timestamp: string | null;
  actor: string | null;
  action: string;
  severity: string;
  resource: string | null;
  target: string | null;
  result: string | null;
  ip: string | null;
  details: Record<string, unknown> | null;
}

export interface PaginatedAudit {
  items: AuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditSummary {
  total: number;
  by_severity: Record<string, number>;
  top_actions: { action: string; count: number }[];
}

export interface ClientItem {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  telegram_username: string | null;
  account_status: string;
  subscription_plan: string | null;
  subscription_active: boolean;
  accounts_count: number;
  licenses_count: number;
  created_at: string | null;
  last_login: string | null;
}

export interface ClientDetail extends ClientItem {
  telegram_id: number | null;
  language: string;
  timezone: string | null;
  subscription: {
    plan: string | null;
    active: boolean;
    start_date: string | null;
    end_date: string | null;
  } | null;
  licenses: { id: string; license_key: string; plan: string; status: string; expires_at: string | null }[];
  accounts: { id: string; broker: string | null; platform: string; login: string | null; account_type: string; active: boolean; engine_status: string }[];
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------
// Overview
export const getOverview = () => authFetch<OverviewResponse>("/api/admin/overview");

// Users
export const listUsers = (params?: string) => authFetch<PaginatedUsers>(`/api/admin/users${params || ""}`);
export const getUser = (id: string) => authFetch(`/api/admin/users/${id}`);
export const createUser = (data: Record<string, unknown>) =>
  authFetch<{ id: string; email: string; audit_id: string; message: string }>("/api/admin/users", {
    method: "POST", body: JSON.stringify(data),
  });
export const updateUser = (id: string, data: Record<string, unknown>) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/users/${id}`, {
    method: "PATCH", body: JSON.stringify(data),
  });
export const suspendUser = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/users/${id}/suspend`, { method: "POST" });
export const activateUser = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/users/${id}/activate`, { method: "POST" });
export const deleteUser = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/users/${id}`, { method: "DELETE" });

// Roles
export const listRoles = () => authFetch<{ items: RoleItem[] }>("/api/admin/roles");
export const getRole = (id: string) => authFetch<RoleItem>(`/api/admin/roles/${id}`);
export const listPermissions = () => authFetch<{ items: PermissionItem[] }>("/api/admin/permissions");
export const assignRole = (data: { user_id: string; role_id: string }) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>("/api/admin/roles/assign", {
    method: "POST", body: JSON.stringify(data),
  });
export const createRole = (data: { name: string; description?: string; permission_ids?: string[] }) =>
  authFetch<{ id: string; audit_id: string; message: string }>("/api/admin/roles", {
    method: "POST", body: JSON.stringify(data),
  });
export const updateRole = (id: string, data: { name?: string; description?: string; permission_ids?: string[] }) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/roles/${id}`, {
    method: "PATCH", body: JSON.stringify(data),
  });
export const deleteRole = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/roles/${id}`, { method: "DELETE" });

// Clients
export const listClients = (params?: string) => authFetch<{ items: ClientItem[]; total: number; limit: number; offset: number }>(`/api/admin/clients${params || ""}`);
export const getClient = (id: string) => authFetch<ClientDetail>(`/api/admin/clients/${id}`);
export const suspendClient = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/users/${id}/suspend`, { method: "POST" });
export const activateClient = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/users/${id}/activate`, { method: "POST" });

// MT5 Accounts (admin — accounts.read/update)
export interface AdminAccount {
  id: string;
  user_id: string;
  user_email: string | null;
  account_type: string;
  broker: string | null;
  prop_firm: string | null;
  program: string | null;
  platform: string;
  server: string | null;
  login: string | null;
  name: string | null;
  account_size: number | null;
  balance_snapshot: number | null;
  equity_snapshot: number | null;
  demo_real: string | null;
  currency: string | null;
  leverage: string | null;
  engine_status: string;
  verified: boolean;
  active: boolean;
  real_trading_enabled: boolean;
  created_at: string | null;
}

export const listAdminAccounts = (params?: string) =>
  authFetch<{ items: AdminAccount[]; total: number }>(`/api/admin/accounts${params || ""}`);
export const updateAdminAccount = (id: string, data: Record<string, unknown>) =>
  authFetch<{ status: string; account_id: string }>(`/api/admin/accounts/${id}`, {
    method: "PATCH", body: JSON.stringify(data),
  });
export const pauseAdminAccount = (id: string) =>
  authFetch<{ status: string; account_id: string }>(`/api/admin/accounts/${id}/pause`, { method: "POST" });
export const resumeAdminAccount = (id: string) =>
  authFetch<{ status: string; account_id: string }>(`/api/admin/accounts/${id}/resume`, { method: "POST" });
export const disableAdminAccount = (id: string) =>
  authFetch<{ status: string; account_id: string }>(`/api/admin/accounts/${id}/disable`, { method: "POST" });

// Audit
export const listAuditLogs = (params?: string) => authFetch<PaginatedAudit>(`/api/admin/audit-logs${params || ""}`);
export const getAuditSummary = () => authFetch<AuditSummary>("/api/admin/audit-logs/summary");

// System health
export const getSystemHealth = () => authFetch<any>("/api/admin/system-health");
export const getSystemEngines = () => authFetch<any[]>("/api/admin/system-health/engines");
export const getHeartbeat = () => authFetch<any>("/api/admin/system-health/heartbeat");
export const getHealthReport = () => authFetch<any>("/api/admin/system-health/report");
export const controlEngine = (action: "restart" | "stop" | "start") =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/system-health/engine/${action}`, { method: "POST" });
export const restartTelegram = () =>
  authFetch<{ success: boolean; audit_id: string; message: string }>("/api/admin/system-health/telegram/restart", { method: "POST" });
export const restartMT5Bridge = () =>
  authFetch<{ success: boolean; audit_id: string; message: string }>("/api/admin/system-health/mt5/restart", { method: "POST" });
export const restartAPI = () =>
  authFetch<{ success: boolean; audit_id: string; message: string }>("/api/admin/system-health/api/restart", { method: "POST" });

// ---------------------------------------------------------------------------
// Notification channels (email + telegram delivery)
// ---------------------------------------------------------------------------
export interface DeliveryRecord {
  id: string;
  event_type: string;
  message: string;
  user_id: string | null;
  severity: string;
  created_at: string | null;
}

export interface EmailStatus {
  email_configured: boolean;
  telegram_configured: boolean;
  telegram_test_mode: boolean;
  email_test_mode: boolean;
  recent_deliveries: DeliveryRecord[];
}

export interface AdminTelegramStatus extends EmailStatus {
  bot_username: string;
  linked_users: number;
}

export const getEmailStatus = () => authFetch<EmailStatus>("/api/admin/emails/status");
export const sendTestEmail = () =>
  authFetch<{ success: boolean; mock: boolean; message: string; audit_id: string }>("/api/admin/emails/test", {
    method: "POST",
    body: JSON.stringify({}),
  });
export const getAdminTelegramStatus = () => authFetch<AdminTelegramStatus>("/api/admin/telegram/status");
export const sendTestTelegram = (chatId: number) =>
  authFetch<{ success: boolean; mock: boolean; message: string; audit_id: string }>("/api/admin/telegram/test", {
    method: "POST",
    body: JSON.stringify({ chat_id: chatId }),
  });

// ---------------------------------------------------------------------------
// Trading
// ---------------------------------------------------------------------------
export const getTradingOverview = () => authFetch<any>("/api/admin/trading/overview");
export const getActiveTrades = (params?: string) => authFetch<{ items: any[]; total: number }>(`/api/admin/trading/active-trades${params || ""}`);
export const getTradeHistory = (params?: string) => authFetch<{ items: any[]; total: number; limit: number; offset: number }>(`/api/admin/trading/history${params || ""}`);
export const getTradingSignals = (params?: string) => authFetch<{ items: any[]; total: number; limit: number; offset: number }>(`/api/admin/trading/signals${params || ""}`);
export const getRiskMonitor = () => authFetch<any>("/api/admin/trading/risk");
export const getTradingPerformance = () => authFetch<any>("/api/admin/trading/performance");
export const getEngineMonitor = () => authFetch<any>("/api/admin/trading/engine");
export const getEngineLogs = (limit = 200) => authFetch<{ items: any[]; total: number }>(`/api/admin/trading/engine/logs?limit=${limit}`);
export const controlTrading = (action: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/trading/control/${action}`, { method: "POST" });
export const closeSymbolTrades = (symbol: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>("/api/admin/trading/control/close-symbol", {
    method: "POST", body: JSON.stringify({ symbol }),
  });
export const getTradeSnapshot = (tradeId: string) =>
  authFetch<{ trade: any; snapshot: any; screenshots: Record<string, string> }>(`/api/admin/trading/trade/${tradeId}/snapshot`);

// ---------------------------------------------------------------------------
// Payment Verification (admin)
// ---------------------------------------------------------------------------
export const listPendingPayments = (params?: { limit?: number; offset?: number }) =>
  authFetch<{ items: any[]; total: number }>(
    `/api/admin/payments/pending?limit=${params?.limit || 50}&offset=${params?.offset || 0}`,
  );

export const approvePayment = (paymentId: string, data?: { internal_notes?: string }) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(
    `/api/admin/payments/${paymentId}/approve`,
    { method: "POST", body: JSON.stringify(data || {}) },
  );

export const rejectPayment = (paymentId: string, rejection_reason: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(
    `/api/admin/payments/${paymentId}/reject`,
    { method: "POST", body: JSON.stringify({ rejection_reason }) },
  );

// ---------------------------------------------------------------------------
// Plans + Subscriptions + Billing
// ---------------------------------------------------------------------------
export const listPlans = () => authFetch<{ items: any[] }>("/api/admin/plans");
export const updatePlan = (planId: string, data: any) =>
  authFetch<{ success: boolean; plan: any }>(`/api/admin/plans/${planId}`, { method: "PUT", body: JSON.stringify(data) });
export const restoreDefaultPlans = () =>
  authFetch<{ success: boolean; items: any[] }>("/api/admin/plans/restore-defaults", { method: "POST" });
export const listSubscriptions = (params?: string) => authFetch<{ items: any[]; total: number }>(`/api/admin/subscriptions${params || ""}`);
export const updateSubscription = (id: string, data: any) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/subscriptions/${id}`, { method: "PATCH", body: JSON.stringify(data) });
export const cancelSubscription = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/subscriptions/${id}/cancel`, { method: "POST" });
export const listPayments = (params?: string) => authFetch<{ items: any[]; total: number }>(`/api/admin/payments${params || ""}`);
// Filtered payments list — /api/admin/payments ignores a status param, so use
// the dedicated filtered endpoint for status/type/currency filtering.
export const listPaymentsFiltered = (params?: string) =>
  authFetch<{ items: any[]; total: number }>(`/api/admin/payments/list${params || ""}`);
export const getRevenueAnalytics = () => authFetch<any>("/api/admin/analytics/revenue");
export const listPromotions = (params?: string) =>
  authFetch<{ items: any[]; total: number }>(`/api/admin/promotions${params || ""}`);
export const createPromotion = (data: any) =>
  authFetch<{ id: string; audit_id: string; message: string }>("/api/admin/promotions", { method: "POST", body: JSON.stringify(data) });
export const updatePromotion = (id: string, data: any) =>
  authFetch<{ success: boolean; promotion: any; audit_id: string }>(`/api/admin/promotions/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deletePromotion = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/promotions/${id}`, { method: "DELETE" });
export const togglePromotion = (id: string) =>
  authFetch<{ success: boolean; active: boolean; audit_id: string }>(`/api/admin/promotions/${id}/toggle`, { method: "POST" });

// ---------------------------------------------------------------------------
// Coupons (admin — coupons.read/create/update/delete)
// ---------------------------------------------------------------------------
export interface CouponItem {
  id: string;
  code: string;
  name: string;
  description: string | null;
  discount_type: "percentage" | "fixed_amount";
  discount_value: number | null;
  currency: string | null;
  valid_from: string | null;
  valid_until: string | null;
  max_redemptions: number | null;
  max_per_user: number;
  min_subscription_value: number | null;
  applicable_plans: string[] | null;
  active: boolean;
  total_redemptions: number;
  total_discount_granted: number;
  created_at: string | null;
}

export const listCoupons = () =>
  authFetch<{ items: CouponItem[]; total: number }>("/api/admin/coupons");
export const createCoupon = (data: Record<string, unknown>) =>
  authFetch<{ success: boolean; coupon: CouponItem }>("/api/admin/coupons", {
    method: "POST", body: JSON.stringify(data),
  });
export const updateCoupon = (id: string, data: Record<string, unknown>) =>
  authFetch<{ success: boolean; coupon: CouponItem }>(`/api/admin/coupons/${id}`, {
    method: "PUT", body: JSON.stringify(data),
  });
export const toggleCoupon = (id: string) =>
  authFetch<{ success: boolean; id: string; code: string; active: boolean }>(`/api/admin/coupons/${id}/toggle`, { method: "POST" });
export const deleteCoupon = (id: string) =>
  authFetch<{ success: boolean; message: string; id: string }>(`/api/admin/coupons/${id}`, { method: "DELETE" });

// ---------------------------------------------------------------------------
// EA Builds (admin publishing — ea.read / ea.publish)
// ---------------------------------------------------------------------------
export interface EABuildAdminItem {
  id: string;
  version: string;
  release_notes: string | null;
  changelog: string | null;
  released_at: string | null;
  windows_available: boolean;
  macos_available: boolean;
  is_latest: boolean;
  windows_file: string | null;
  approved: boolean;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
}

export const listEABuilds = () =>
  authFetch<{ items: EABuildAdminItem[]; total: number }>("/api/admin/ea-builds");
export const createEABuild = (data: { version: string; release_notes?: string; changelog?: string }) =>
  authFetch<{ id: string; version: string; audit_id: string; message: string }>("/api/admin/ea-builds", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const updateEABuild = (id: string, data: { release_notes?: string; changelog?: string }) =>
  authFetch<{ success: boolean; id: string; version: string; audit_id: string; message: string }>(
    `/api/admin/ea-builds/${id}`,
    { method: "PATCH", body: JSON.stringify(data) },
  );
export const setLatestEABuild = (id: string) =>
  authFetch<{ success: boolean; id: string; version: string; audit_id: string; message: string }>(
    `/api/admin/ea-builds/${id}/set-latest`,
    { method: "POST" },
  );
export const deleteEABuild = (id: string) =>
  authFetch<{ success: boolean; version: string; file_removed: boolean; audit_id: string; message: string }>(
    `/api/admin/ea-builds/${id}`,
    { method: "DELETE" },
  );
export const approveEABuild = (id: string) =>
  authFetch<{ success: boolean; id: string; version: string; audit_id: string; message: string }>(
    `/api/admin/ea-builds/${id}/approve`,
    { method: "POST" },
  );
export const rejectEABuild = (id: string, reason?: string) =>
  authFetch<{ success: boolean; id: string; version: string; audit_id: string; message: string }>(
    `/api/admin/ea-builds/${id}/reject`,
    { method: "POST", body: JSON.stringify({ reason: reason || "" }) },
  );

// Multipart upload: keep the auth header, but let the browser set the
// multipart boundary (never send a manual Content-Type for FormData).
export async function uploadEABuildFile(buildId: string, file: File) {
  const token = getAccessToken();
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API_BASE}/api/admin/ea-builds/${buildId}/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: fd,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `API ${res.status}: upload failed`);
  return body as { success: boolean; version: string; windows_file: string; size_bytes: number; message: string };
}

// ---------------------------------------------------------------------------
// Permission check (coarse frontend gate; backend require_permission is
// authoritative). Contract: POST /auth/check-permission { resource, action }.
// ---------------------------------------------------------------------------
export async function checkPermission(resource: string, action: string): Promise<boolean> {
  try {
    const res = await authFetch<{ resource: string; action: string; allowed: boolean }>(
      "/auth/check-permission",
      { method: "POST", body: JSON.stringify({ resource, action }) },
    );
    return res.allowed;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Licenses (frozen admin contract)
// ---------------------------------------------------------------------------
export interface LicenseItem {
  id: string;
  user_id: string;
  license_key: string;
  plan: string;
  status: string;
  max_accounts: number;
  expires_at: string | null;
  bound_account_id: string | null;
  bound_at: string | null;
  telegram_id: number | null;
  transfer_locked: boolean;
  created_at: string | null;
  telegram_username?: string | null;
}

export const listLicenses = (params?: string) =>
  authFetch<{ items: LicenseItem[]; total: number }>(`/api/admin/licenses${params || ""}`);
export const createLicense = (data: { user_id: string; plan: string; max_accounts: number; expires_in_days: number | null }) =>
  authFetch<{ id: string; audit_id: string; message: string }>("/api/admin/licenses", {
    method: "POST", body: JSON.stringify(data),
  });
export const licenseAction = (id: string, action: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/licenses/${id}/${action}`, { method: "POST" });
export const getLicense = (id: string) => authFetch<Record<string, unknown>>(`/api/admin/licenses/${id}`);

// ---------------------------------------------------------------------------
// News + announcements (frozen admin contract)
// ---------------------------------------------------------------------------
export interface NewsItem {
  id: string;
  title: string;
  body: string;
  category: string;
  published: boolean;
  telegram_sent: boolean;
  created_at: string | null;
}

export interface EngineStatus {
  running: boolean;
  last_fetch: string | null;
  last_fetch_ago_sec: number | null;
  total_events: number;
  upcoming_high: {
    time: string | null;
    currency: string;
    event: string;
    impact: string;
    forecast: string;
    previous: string;
  }[];
  usd_events_today: number;
  cache_exists: boolean;
}

export const listNews = () => authFetch<{ items: NewsItem[]; total: number }>("/api/admin/news");
export const getEngineStatus = () => authFetch<EngineStatus>("/api/admin/news/engine-status");
export const createNews = (data: { title: string; body: string; category: string; published: boolean }) =>
  authFetch<{ id: string; audit_id: string; message: string }>("/api/admin/news", {
    method: "POST", body: JSON.stringify(data),
  });
export const updateNews = (id: string, data: { title: string; body: string; category: string; published: boolean }) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/news/${id}`, {
    method: "PATCH", body: JSON.stringify(data),
  });
export const deleteNews = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/news/${id}`, { method: "DELETE" });
export const broadcastNews = (id: string) =>
  authFetch<{ broadcasted: number }>(`/api/admin/news/${id}/broadcast`, { method: "POST" });

// ---------------------------------------------------------------------------
// Support tickets (shared records — client, Telegram, admin, owner)
// ---------------------------------------------------------------------------
export interface AdminTicketMessage {
  id: string;
  author_user_id: string | null;
  author_role: string;
  author_name: string | null;
  kind: string;
  is_internal: boolean;
  body: string;
  created_at: string | null;
}

export interface AdminTicket {
  id: string;
  ticket_number: string;
  user_id: string;
  subject: string;
  description: string;
  category: string;
  status: string;
  priority: string;
  escalated: boolean;
  escalated_by: string | null;
  escalated_at: string | null;
  escalation_target: string | null;
  escalation_reason: string | null;
  assignee_id: string | null;
  assigned_at: string | null;
  source: string;
  admin_reply: string | null;
  replied_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  closed_at: string | null;
  closed_by: string | null;
  resolved_at: string | null;
  messages: AdminTicketMessage[];
  user: {
    id: string;
    email: string | null;
    telegram_id: number | null;
    telegram_username: string | null;
    first_name: string | null;
    last_name: string | null;
    language: string;
    status: string | null;
    created_at: string | null;
  } | null;
  license: { license_key: string | null; plan: string | null } | null;
  assignee: {
    id: string;
    first_name: string | null;
    last_name: string | null;
    email: string | null;
    role: string | null;
  } | null;
}

export interface AdminTicketListResponse {
  success: boolean;
  tickets: AdminTicket[];
  total: number;
  page: number;
  limit: number;
}

export interface AdminTicketDetailResponse {
  success: boolean;
  ticket: AdminTicket;
}

export interface AdminTicketMutation {
  success: boolean;
  audit_id: string;
  message: string;
}

export const listTickets = (params?: string) =>
  authFetch<AdminTicketListResponse>(`/api/admin/tickets${params || ""}`);
export const getTicket = (id: string) => authFetch<AdminTicketDetailResponse>(`/api/admin/tickets/${id}`);
export const replyTicket = (id: string, message: string, isInternal = false) =>
  authFetch<AdminTicketMutation>(`/api/admin/tickets/${id}/reply`, {
    method: "POST", body: JSON.stringify({ message, is_internal: isInternal }),
  });
export const updateTicket = (id: string, data: { status?: string; priority?: string; category?: string }) =>
  authFetch<AdminTicketMutation>(`/api/admin/tickets/${id}`, {
    method: "PATCH", body: JSON.stringify(data),
  });
export const assignTicket = (id: string, assigneeId: string) =>
  authFetch<AdminTicketMutation & { assignee: AdminTicket["assignee"] }>(`/api/admin/tickets/${id}/assign`, {
    method: "POST", body: JSON.stringify({ assignee_id: assigneeId }),
  });
export const escalateTicket = (id: string, target = "admin", reason = "") =>
  authFetch<AdminTicketMutation & { escalated_at: string | null }>(`/api/admin/tickets/${id}/escalate`, {
    method: "POST", body: JSON.stringify({ target, reason }),
  });
export const banTicketUser = (id: string) =>
  authFetch<AdminTicketMutation>(`/api/admin/tickets/${id}/ban`, { method: "POST" });

// ---------------------------------------------------------------------------
// Site Settings
// ---------------------------------------------------------------------------
export interface SettingField {
  key: string;
  type: "string" | "number" | "boolean" | "select" | "color" | "password" | "textarea" | "json";
  label: string;
  default?: unknown;
  options?: string[];
  help?: string;
  is_secret?: boolean;
}

export const getSettingsSchema = () =>
  authFetch<{ categories: string[]; groups: Record<string, SettingField[]> }>("/api/admin/settings/schema");
export const getSettings = () =>
  authFetch<{ settings: Record<string, unknown> }>("/api/admin/settings");
export const updateSettings = (updates: Record<string, unknown>) =>
  authFetch<{ success: boolean; updated: string[]; settings: Record<string, unknown> }>("/api/admin/settings", {
    method: "PUT", body: JSON.stringify({ updates }),
  });
