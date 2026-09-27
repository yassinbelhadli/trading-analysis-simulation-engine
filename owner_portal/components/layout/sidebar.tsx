"use client";

import { useRouter } from "next/navigation";
import { logout } from "@/lib/auth";
import { useTheme } from "@/components/ThemeProvider";
import { AppSidebar, type NavGroup } from "@ds/components/AppShell";
import { Icon, type IconName } from "@ds/components/Icon";
import { Button } from "@ds/components/ui";

/**
 * Owner Portal navigation — executive control plane (V2).
 * Icons are stroke icons from the shared V2 set (no emoji). Permission gating
 * stays page-level via OwnerPermissionGuard + the authoritative backend
 * require_permission; this nav is a UX surface only.
 */
export const OWNER_NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [{ href: "/dashboard", label: "Dashboard", icon: "dashboard" as IconName }],
  },
  {
    label: "Commercial",
    items: [
      { href: "/dashboard/revenue", label: "Revenue", icon: "dollar" as IconName },
      { href: "/dashboard/billing", label: "Billing", icon: "credit-card" as IconName },
      { href: "/dashboard/billing/payments", label: "Payment Verification", icon: "shield-check" as IconName },
      { href: "/dashboard/billing/payment-methods", label: "Payment Methods", icon: "wallet" as IconName },
      { href: "/dashboard/promotions", label: "Promotions", icon: "tag" as IconName },
    ],
  },
  {
    label: "Control Plane",
    items: [
      { href: "/dashboard/users", label: "Users", icon: "users" as IconName },
      { href: "/dashboard/roles", label: "Roles & Permissions", icon: "shield-check" as IconName },
      { href: "/dashboard/audit", label: "Audit Logs", icon: "scroll" as IconName },
      { href: "/dashboard/downloads", label: "Downloads", icon: "download" as IconName },
      { href: "/dashboard/support", label: "Support", icon: "lifebuoy" as IconName },
      { href: "/dashboard/engine", label: "Engine Control", icon: "zap" as IconName },
      { href: "/dashboard/system", label: "System Health", icon: "gauge" as IconName },
      { href: "/dashboard/system/integrations", label: "Integrations", icon: "plug" as IconName },
      { href: "/dashboard/settings", label: "Safe Settings", icon: "settings" as IconName },
      { href: "/dashboard/settings/secrets", label: "Secrets", icon: "lock" as IconName },
    ],
  },
  {
    label: "Communications",
    items: [
      { href: "/dashboard/news", label: "News", icon: "newspaper" as IconName },
      { href: "/dashboard/alerts", label: "Alerts", icon: "bell" as IconName },
    ],
  },
];

export default function OwnerSidebar() {
  const router = useRouter();
  const { theme, toggle } = useTheme();

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <AppSidebar
      groups={OWNER_NAV_GROUPS}
      logoHref="/dashboard"
      footer={
        <div className="flex flex-col gap-1">
          <button
            onClick={toggle}
            className="flex items-center gap-2.5 px-2.5 h-9 rounded-lg text-[13px] text-ink-soft hover:bg-hover hover:text-ink transition-colors"
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} className="h-4 w-4" />
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <Button
            variant="ghost"
            icon="logout"
            className="w-full justify-start px-2.5 h-9 text-[13px] hover:text-danger"
            onClick={handleLogout}
          >
            Sign out
          </Button>
        </div>
      }
    />
  );
}
