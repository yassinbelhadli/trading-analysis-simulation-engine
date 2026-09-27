"use client";

import { useRouter } from "next/navigation";
import { logout } from "@/lib/auth";
import { useTheme } from "@/components/ThemeProvider";
import { useLocale } from "@/components/LocaleContext";
import { AppSidebar, type NavGroup } from "@ds/components/AppShell";
import { Icon, type IconName } from "@ds/components/Icon";
import { Button } from "@ds/components/ui";

export const CLIENT_NAV_GROUPS: NavGroup[] = [
  {
    label: "Account",
    items: [
      { href: "/dashboard", label: "Overview", icon: "dashboard" as IconName },
      { href: "/dashboard/activity", label: "Trading Activity", icon: "activity" as IconName },
      { href: "/dashboard/performance", label: "Performance", icon: "chart" as IconName },
    ],
  },
  {
    label: "Trading",
    items: [
      { href: "/dashboard/accounts", label: "MT5 Accounts", icon: "server" as IconName },
      { href: "/dashboard/downloads", label: "EA Updates", icon: "download" as IconName },
    ],
  },
  {
    label: "Manage",
    items: [
      { href: "/dashboard/license", label: "License", icon: "key" as IconName },
      { href: "/dashboard/subscription", label: "Subscription", icon: "credit-card" as IconName },
      { href: "/dashboard/billing", label: "Billing", icon: "receipt" as IconName },
      { href: "/dashboard/notifications", label: "Notifications", icon: "bell" as IconName },
      { href: "/dashboard/telegram", label: "Telegram", icon: "send" as IconName },
      { href: "/dashboard/news", label: "Economic Calendar", icon: "calendar" as IconName },
    ],
  },
  {
    label: "Account & Help",
    items: [
      { href: "/dashboard/profile", label: "Profile", icon: "user" as IconName },
      { href: "/dashboard/settings", label: "Settings", icon: "settings" as IconName },
      { href: "/dashboard/security", label: "Security", icon: "shield" as IconName },
      { href: "/dashboard/support", label: "Support", icon: "lifebuoy" as IconName },
    ],
  },
];

// Key for each nav item label, used for translation.
const NAV_LABEL_KEYS: Record<string, string> = {
  "Account": "nav.account",
  "Trading": "nav.trading",
  "Manage": "nav.manage",
  "Account & Help": "nav.accountHelp",
  "Overview": "nav.overview",
  "Trading Activity": "nav.activity",
  "Performance": "nav.performance",
  "MT5 Accounts": "nav.accounts",
  "EA Updates": "nav.downloads",
  "License": "nav.license",
  "Subscription": "nav.subscription",
  "Billing": "nav.billing",
  "Notifications": "nav.notifications",
  "Telegram": "nav.telegram",
  "Economic Calendar": "nav.news",
  "Profile": "nav.profile",
  "Settings": "nav.settings",
  "Security": "nav.security",
  "Support": "nav.support",
};

export function useTranslatedNavGroups(): NavGroup[] {
  const { t } = useLocale();
  return CLIENT_NAV_GROUPS.map((g) => ({
    ...g,
    label: t(NAV_LABEL_KEYS[g.label ?? ""] || (g.label ?? "")),
    items: g.items.map((item) => ({
      ...item,
      label: t(NAV_LABEL_KEYS[item.label ?? ""] || (item.label ?? "")),
    })),
  }));
}

export default function ClientSidebar() {
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const { t } = useLocale();
  const groups = useTranslatedNavGroups();

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  return (
    <AppSidebar
      groups={groups}
      logoHref="/dashboard"
      footer={
        <div className="flex flex-col gap-1">
          <button
            onClick={toggle}
            className="flex items-center gap-2.5 px-2.5 h-9 rounded-lg text-[13px] text-ink-soft hover:bg-hover hover:text-ink transition-colors"
          >
            <Icon name={theme === "dark" ? "sun" : "moon"} className="h-4 w-4" />
            {theme === "dark" ? t("common.lightMode") : t("common.darkMode")}
          </button>
          <Button
            variant="ghost"
            icon="logout"
            className="w-full justify-start px-2.5 h-9 text-[13px] hover:text-danger"
            onClick={handleLogout}
          >
            {t("common.signOut")}
          </Button>
        </div>
      }
    />
  );
}