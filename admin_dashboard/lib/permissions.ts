"use client";

export interface MenuItem {
  href: string;
  label: string;
  icon: string;
  permission?: string;
  roles?: readonly string[];
}

export interface MenuGroup {
  label: string;
  items: MenuItem[];
}

export const ROLES = ["owner", "admin", "support", "risk_manager", "analyst", "billing", "notification_mgr"] as const;

/**
 * Coarse UX navigation filter — this is NOT an authorization mechanism.
 * The backend `require_permission` (security/access_control.py) is the only
 * enforcement point. `roles` mirrors ROLE_PERMISSIONS only for nav visibility;
 * `permission` is documented for page-level PermissionGuard checks.
 */
const MENU_GROUPS: MenuGroup[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "dashboard", permission: "admin.overview", roles: ["owner", "admin"] },
    ],
  },
  {
    label: "Commercial",
    items: [
      { href: "/dashboard/clients", label: "Clients", icon: "users", permission: "clients.read", roles: ["owner", "admin", "support", "risk_manager", "billing", "notification_mgr"] },
      { href: "/dashboard/licenses", label: "Licenses", icon: "key", permission: "licenses.read", roles: ["owner", "admin"] },
      { href: "/dashboard/subscriptions", label: "Plans", icon: "scroll", permission: "subscriptions.read", roles: ["owner", "admin", "billing"] },
      { href: "/dashboard/payments", label: "Payments", icon: "credit-card", permission: "billing.read", roles: ["owner", "admin", "billing"] },
      { href: "/dashboard/payments/verify", label: "Payment Verification", icon: "check-circle", permission: "billing.read", roles: ["owner", "admin", "billing"] },
      { href: "/dashboard/promotions", label: "Promotions", icon: "tag", permission: "subscriptions.read", roles: ["owner", "admin", "billing"] },
    ],
  },
  {
    label: "Trading",
    items: [
      { href: "/dashboard/trading", label: "Overview", icon: "chart", permission: "trades.read", roles: ["owner"] },
      { href: "/dashboard/trading/trades", label: "Active Trades", icon: "activity", permission: "trades.read", roles: ["owner"] },
      { href: "/dashboard/trading/history", label: "Trade History", icon: "file-text", permission: "trades.read", roles: ["owner"] },
      { href: "/dashboard/trading/signals", label: "Signals", icon: "search", permission: "trades.read", roles: ["owner"] },
      { href: "/dashboard/trading/risk", label: "Risk Monitor", icon: "alert-triangle", permission: "trades.read", roles: ["owner"] },
      { href: "/dashboard/trading/performance", label: "Performance", icon: "chart-pie", permission: "analytics.read", roles: ["owner"] },
      { href: "/dashboard/trading/engine", label: "Engine", icon: "cpu", permission: "engine.read", roles: ["owner"] },
    ],
  },
  {
    label: "Support & Comms",
    items: [
      { href: "/dashboard/tickets", label: "Support Tickets", icon: "lifebuoy", permission: "tickets.read", roles: ["owner", "admin", "support"] },
      { href: "/dashboard/ea-builds", label: "Downloads", icon: "wrench", roles: ["owner", "admin"] },
      { href: "/dashboard/telegram", label: "Telegram", icon: "megaphone", permission: "telegram.send", roles: ["owner", "admin", "notification_mgr"] },
      { href: "/dashboard/news", label: "News", icon: "newspaper", permission: "admin.overview", roles: ["owner", "admin"] },
      { href: "/dashboard/notifications", label: "Notifications", icon: "bell", permission: "emails.read", roles: ["owner", "admin", "notification_mgr"] },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/dashboard/system", label: "System Health", icon: "gauge", permission: "system.health.read", roles: ["owner", "admin", "support", "risk_manager"] },
      { href: "/dashboard/audit", label: "Audit Logs", icon: "scroll", permission: "audit.read", roles: ["owner", "admin"] },
      { href: "/dashboard/roles", label: "Roles & Permissions", icon: "shield-check", permission: "roles.read", roles: ["owner"] },
      { href: "/dashboard/users", label: "Users", icon: "users", permission: "users.read", roles: ["owner", "admin"] },
      { href: "/dashboard/security", label: "Security", icon: "lock", roles: ROLES },
      { href: "/dashboard/settings", label: "Settings", icon: "settings", permission: "system.settings", roles: ["owner", "admin"] },
    ],
  },
  {
    label: "Owner",
    items: [
      { href: "/dashboard/revenue", label: "Revenue", icon: "trending-up", permission: "admin.overview", roles: ["owner"] },
    ],
  },
];

export function getFilteredGroups(user_permissions?: string[] | null): MenuGroup[] {
  if (!user_permissions || user_permissions.length === 0) return [];
  const hasAll = user_permissions.includes("*");
  return MENU_GROUPS
    .map((g) => ({
      ...g,
      items: g.items.filter((item) => {
        if (hasAll) return true;
        if (!item.permission) return true;
        return user_permissions.includes(item.permission);
      }),
    }))
    .filter((g) => g.items.length > 0);
}
