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
// Fetch a proof file (admin route) with auth and return an object URL.
// The stored proof URL is the client route; the owner must view it through
// the admin route, which requires the owner's Bearer token (an <img src>
// cannot send headers, so we fetch as a blob and render the object URL).
// ---------------------------------------------------------------------------
export async function fetchProofObjectUrl(proofUrl: string): Promise<string> {
  const adminPath = proofUrl.replace(
    "/api/client/uploads/proofs/",
    "/api/admin/uploads/proofs/",
  );
  let token = getAccessToken();
  const doFetch = (tok: string | null) => {
    const h: Record<string, string> = {};
    if (tok) h["Authorization"] = `Bearer ${tok}`;
    return fetch(`${API_BASE}${adminPath}`, { headers: h });
  };
  let res = await doFetch(token);
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      token = newToken;
      res = await doFetch(token);
    }
  }
  if (!res.ok) throw new Error(`Proof fetch failed: ${res.status}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
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

export interface SettingField {
  key: string;
  type: "string" | "number" | "boolean" | "select" | "color" | "password" | "textarea" | "json";
  label: string;
  default?: unknown;
  options?: string[];
  help?: string;
  is_secret?: boolean;
}

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

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------
export const getOverview = () => authFetch<OverviewResponse>("/api/admin/overview");

// ---------------------------------------------------------------------------
// Users (control)
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Roles & Permissions
// ---------------------------------------------------------------------------
export const listRoles = () => authFetch<{ items: RoleItem[] }>("/api/admin/roles");
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

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------
export const listAuditLogs = (params?: string) => authFetch<PaginatedAudit>(`/api/admin/audit-logs${params || ""}`);
export const getAuditSummary = () => authFetch<AuditSummary>("/api/admin/audit-logs/summary");

// ---------------------------------------------------------------------------
// System Health
// ---------------------------------------------------------------------------
export const getSystemHealth = () => authFetch<any>("/api/admin/system-health");
export const getSystemEngines = () => authFetch<any[]>("/api/admin/system-health/engines");
export const getHeartbeat = () => authFetch<any>("/api/admin/system-health/heartbeat");
export const getHealthReport = () => authFetch<any>("/api/admin/system-health/report");
export const controlEngine = (action: "restart" | "stop" | "start") =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/system-health/engine/${action}`, { method: "POST" });

// ---------------------------------------------------------------------------
// Integration channels (notifications admin endpoints — status only, never secrets)
// ---------------------------------------------------------------------------
export const getTelegramChannelStatus = () =>
  authFetch<{
    email_configured: boolean;
    telegram_configured: boolean;
    telegram_test_mode: boolean;
    email_test_mode: boolean;
    bot_username: string;
    linked_users: number;
    recent_deliveries: { id: string; event_type: string; message: string | null; created_at: string | null }[];
  }>("/api/admin/telegram/status");
export const getEmailChannelStatus = () =>
  authFetch<{
    email_configured: boolean;
    telegram_configured: boolean;
    telegram_test_mode: boolean;
    email_test_mode: boolean;
    recent_deliveries: { id: string; event_type: string; message: string | null; created_at: string | null }[];
  }>("/api/admin/emails/status");

// ---------------------------------------------------------------------------
// Engine Control (frozen /api/admin/trading/control/*)
// ---------------------------------------------------------------------------
export const controlTrading = (action: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/trading/control/${action}`, { method: "POST" });
export const closeSymbolTrades = (symbol: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>("/api/admin/trading/control/close-symbol", {
    method: "POST", body: JSON.stringify({ symbol }),
  });
export const getEngineMonitor = () => authFetch<any>("/api/admin/trading/engine");
export const getEngineLogs = (limit = 200) => authFetch<{ items: any[]; total: number }>(`/api/admin/trading/engine/logs?limit=${limit}`);

// ---------------------------------------------------------------------------
// Site Settings (safe keys only — secret deny-list enforced in UI + lib)
// ---------------------------------------------------------------------------
export const getSettingsSchema = () =>
  authFetch<{ categories: string[]; groups: Record<string, SettingField[]> }>("/api/admin/settings/schema");
export const getSettings = () =>
  authFetch<{ settings: Record<string, unknown> }>("/api/admin/settings");

// Code-level secret deny-list (defense in depth, §7.3 of Phase 5 spec).
// Prevents secret/sensitive keys from ever being sent to PUT /settings.
// The schema's `is_secret` flags are the primary guard; this set is a hard
// fallback for any key whose schema flag may be absent or mis-set.
const SECRET_DENYLIST = new Set<string>([
  "telegram.bot_token",
  "email.smtp_pass",
  "security.jwt_secret",
  "security.encryption_key",
  "api.mt5_credentials",
  "database.url",
  "news.api_key",
]);

export function isDeniedSecret(key: string): boolean {
  return SECRET_DENYLIST.has(key);
}

export const updateSettings = (updates: Record<string, unknown>) =>
  authFetch<{ success: boolean; updated: string[]; settings: Record<string, unknown> }>("/api/admin/settings", {
    method: "PUT", body: JSON.stringify({ updates }),
  });

// Strips any secret/sensitive keys before a settings write. Called by the
// settings page; defensive so no secret reaches the PUT contract.
export function sanitizeSettingsPayload(updates: Record<string, unknown>, schemaGroups: Record<string, SettingField[]>): Record<string, unknown> {
  const safe: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(updates)) {
    if (isDeniedSecret(key)) continue;
    let isSecret = false;
    for (const group of Object.values(schemaGroups)) {
      const field = group.find((f) => f.key === key);
      if (field?.is_secret) { isSecret = true; break; }
    }
    if (isSecret) continue;
    if (value === "••••••••") continue; // masked placeholder — never echo back
    safe[key] = value;
  }
  return safe;
}

// ---------------------------------------------------------------------------
// Plans + Subscriptions + Billing (oversight)
// ---------------------------------------------------------------------------
export const listPlans = () => authFetch<{ items: any[] }>("/api/admin/plans");
export const createPlan = (data: any) =>
  authFetch<{ success: boolean; plan: any }>("/api/admin/plans", { method: "POST", body: JSON.stringify(data) });
export const updatePlan = (planId: string, data: any) =>
  authFetch<{ success: boolean; plan: any }>(`/api/admin/plans/${planId}`, { method: "PUT", body: JSON.stringify(data) });
export const deletePlan = (planId: string) =>
  authFetch<{ success: boolean; message: string }>(`/api/admin/plans/${planId}`, { method: "DELETE" });
export const archivePlan = (planId: string) =>
  authFetch<{ success: boolean; plan: any }>(`/api/admin/plans/${planId}`, { method: "PUT", body: JSON.stringify({ is_archived: true }) });
export const activatePlan = (planId: string) =>
  authFetch<{ success: boolean; plan: any }>(`/api/admin/plans/${planId}`, { method: "PUT", body: JSON.stringify({ is_active: true }) });
export const deactivatePlan = (planId: string) =>
  authFetch<{ success: boolean; plan: any }>(`/api/admin/plans/${planId}`, { method: "PUT", body: JSON.stringify({ is_active: false }) });
export const restoreDefaultPlans = () =>
  authFetch<{ success: boolean; items: any[] }>("/api/admin/plans/restore-defaults", { method: "POST" });
export const listSubscriptions = (params?: string) => authFetch<{ items: any[]; total: number }>(`/api/admin/subscriptions${params || ""}`);
export const cancelSubscription = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/subscriptions/${id}/cancel`, { method: "POST" });
export const listPayments = (params?: string) => authFetch<{ items: any[]; total: number }>(`/api/admin/payments${params || ""}`);
export const listPendingPayments = (params?: string) => authFetch<{ items: any[]; total: number }>(`/api/admin/payments/pending${params || ""}`);
export const approvePayment = (paymentId: string, data?: { internal_notes?: string }) =>
  authFetch<{ success: boolean; payment: any }>(`/api/admin/payments/${paymentId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {}),
  });
export const rejectPayment = (paymentId: string, rejection_reason: string) =>
  authFetch<{ success: boolean; payment: any }>(`/api/admin/payments/${paymentId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rejection_reason }),
  });
export const getRevenueAnalytics = () => authFetch<any>("/api/admin/analytics/revenue");

// ---------------------------------------------------------------------------
// Coupons
// ---------------------------------------------------------------------------
export const listCoupons = () =>
  authFetch<{ items: any[]; total: number }>("/api/admin/coupons");
export const createCoupon = (data: any) =>
  authFetch<{ success: boolean; coupon: any }>("/api/admin/coupons", { method: "POST", body: JSON.stringify(data) });
export const updateCoupon = (couponId: string, data: any) =>
  authFetch<{ success: boolean; coupon: any }>(`/api/admin/coupons/${couponId}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteCoupon = (couponId: string) =>
  authFetch<{ success: boolean; message: string; id: string }>(`/api/admin/coupons/${couponId}`, { method: "DELETE" });
export const toggleCoupon = (couponId: string) =>
  authFetch<{ success: boolean; id: string; code: string; active: boolean }>(`/api/admin/coupons/${couponId}/toggle`, { method: "POST" });
export const validateCoupon = (data: { code: string; plan_id: string; currency: string }) =>
  authFetch<{ valid: boolean; coupon_code: string; original_price: number; discount_amount: number; final_price: number; message: string }>("/api/admin/coupons/validate", { method: "POST", body: JSON.stringify(data) });

// ---------------------------------------------------------------------------
// Promotions
// ---------------------------------------------------------------------------
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
// Support tickets (shared records — same API contract as the admin dashboard)
// ---------------------------------------------------------------------------
export interface OwnerTicketMessage {
  id: string;
  author_user_id: string | null;
  author_role: string;
  author_name: string | null;
  kind: string;
  is_internal: boolean;
  body: string;
  created_at: string | null;
}

export interface OwnerTicket {
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
  messages: OwnerTicketMessage[];
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

export interface TicketMetrics {
  total: number;
  open: number;
  in_progress: number;
  resolved: number;
  closed: number;
  escalated: number;
  urgent: number;
}

export const listTickets = (params?: string) =>
  authFetch<{ success: boolean; tickets: OwnerTicket[]; total: number; page: number; limit: number }>(
    `/api/admin/tickets${params || ""}`,
  );
export const getTicket = (id: string) =>
  authFetch<{ success: boolean; ticket: OwnerTicket }>(`/api/admin/tickets/${id}`);
export const getTicketMetrics = () =>
  authFetch<{ success: boolean; metrics: TicketMetrics }>("/api/admin/tickets/metrics");
export const replyTicket = (id: string, message: string, isInternal = false) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/tickets/${id}/reply`, {
    method: "POST", body: JSON.stringify({ message, is_internal: isInternal }),
  });
export const updateTicket = (id: string, data: { status?: string; priority?: string; category?: string }) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/tickets/${id}`, {
    method: "PATCH", body: JSON.stringify(data),
  });
export const assignTicket = (id: string, assigneeId: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/tickets/${id}/assign`, {
    method: "POST", body: JSON.stringify({ assignee_id: assigneeId }),
  });
export const escalateTicket = (id: string, target = "admin", reason = "") =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/tickets/${id}/escalate`, {
    method: "POST", body: JSON.stringify({ target, reason }),
  });
export const banTicketUser = (id: string) =>
  authFetch<{ success: boolean; audit_id: string; message: string }>(`/api/admin/tickets/${id}/ban`, { method: "POST" });

// ---------------------------------------------------------------------------
// News + Broadcast
// ---------------------------------------------------------------------------
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
// Payment Method Configs (owner portal — configurable payment instructions)
// ---------------------------------------------------------------------------
export const listPaymentConfigs = () =>
  authFetch<{ configs: PaymentConfig[] }>("/api/admin/payment-configs");

export const getPaymentConfig = (methodId: string) =>
  authFetch<PaymentConfig>(`/api/admin/payment-configs/${methodId}`);

export const updatePaymentConfig = (methodId: string, data: Partial<PaymentConfig>) =>
  authFetch<{ success: boolean; config: PaymentConfig }>(`/api/admin/payment-configs/${methodId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const createPaymentConfig = (data: Partial<PaymentConfig>) =>
  authFetch<{ success: boolean; config: PaymentConfig }>("/api/admin/payment-configs", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const archivePaymentConfig = (methodId: string) =>
  authFetch<{ success: boolean; archived: string }>(`/api/admin/payment-configs/${methodId}`, {
    method: "DELETE",
  });

// ---------------------------------------------------------------------------
// Payment method configuration types (configuration-driven payment methods)
// ---------------------------------------------------------------------------

/** Field type catalogue — the owner picks from these; the client form renders
 *  the matching input dynamically. Adding a type here is the ONLY code change
 *  ever needed to support a new input kind. */
export const FIELD_TYPES = [
  { value: "text", label: "Text" },
  { value: "number", label: "Number" },
  { value: "phone", label: "Phone" },
  { value: "date", label: "Date" },
  { value: "datetime", label: "Date & Time" },
  { value: "email", label: "Email" },
  { value: "image", label: "Image / File" },
] as const;

export type FieldType = (typeof FIELD_TYPES)[number]["value"];

export interface ClientFieldDef {
  key: string;
  label: string;
  type: FieldType;
  required: boolean;
  placeholder?: string;
  validation?: string;
}

export interface InfoBlock {
  label: string;
  value: string;
}

export interface PaymentConfig {
  id: string;
  method_id: string;
  method_type: string;
  display_name: string;
  beneficiary_name: string | null;
  account_rib: string | null;
  phone_number: string | null;
  branch: string | null;
  instructions: string | null;
  reference_instructions: string | null;
  reference_required: boolean;
  required_fields: string[] | null;
  optional_fields: string[] | null;
  wallet_address: string | null;
  network: string | null;
  expires_hours: number;
  description: string | null;
  information: InfoBlock[] | null;
  client_fields: ClientFieldDef[] | null;
  receipt_required: boolean;
  currencies: string[] | null;
  provider_name: string | null;
  gateway_status: string | null;
  is_active: boolean;
  display_order: number;
  archived: boolean;
  created_at: string | null;
  updated_at: string | null;
}
