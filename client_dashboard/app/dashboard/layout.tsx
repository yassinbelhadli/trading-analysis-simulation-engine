"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import ClientSidebar, { CLIENT_NAV_GROUPS, useTranslatedNavGroups } from "@/components/ClientSidebar";
import ClientAuthGuard from "@/components/ClientAuthGuard";
import { AppShell, AppTopbar } from "@ds/components/AppShell";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Icon } from "@ds/components/Icon";
import { logout } from "@/lib/auth";
import { useTheme } from "@/components/ThemeProvider";
import { LocaleProvider, useLocale } from "@/components/LocaleContext";
import LocaleBar from "@/components/LocaleBar";

const TITLE_KEYS: Record<string, string> = {
  "/dashboard": "nav.overview",
  "/dashboard/activity": "nav.activity",
  "/dashboard/performance": "nav.performance",
  "/dashboard/accounts": "nav.accounts",
  "/dashboard/downloads": "nav.downloads",
  "/dashboard/license": "nav.license",
  "/dashboard/subscription": "nav.subscription",
  "/dashboard/billing": "nav.billing",
  "/dashboard/notifications": "nav.notifications",
  "/dashboard/telegram": "nav.telegram",
  "/dashboard/news": "nav.news",
  "/dashboard/profile": "nav.profile",
  "/dashboard/settings": "nav.settings",
  "/dashboard/security": "nav.security",
  "/dashboard/support": "nav.support",
};

function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const navGroups = useTranslatedNavGroups();

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const currentTitle =
    t(TITLE_KEYS[pathname] || "nav.clientPortal") ??
    (pathname.startsWith("/dashboard/accounts/") ? t("nav.accountDetail") : t("nav.clientPortal"));

  return (
    <AppShell
      sidebar={<ClientSidebar />}
      topbar={
        <AppTopbar
          title={currentTitle}
          left={<BrandLogo href="/dashboard" height={22} className="lg:hidden" />}
          right={
            <>
              <LocaleBar />
              <button
                onClick={toggle}
                aria-label="Toggle theme"
                className="h-8 w-8 rounded-md flex items-center justify-center text-ink-soft hover:bg-hover hover:text-ink"
              >
                <Icon name={theme === "dark" ? "sun" : "moon"} className="h-4 w-4" />
              </button>
            </>
          }
          mobileNav={
            <nav className="flex flex-col gap-0.5" aria-label="Mobile navigation">
              {navGroups.map((g) => (
                <div key={g.label} className="mb-3">
                  <p className="px-2 mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                    {g.label}
                  </p>
                  {g.items.map((item) => {
                    const active =
                      item.href === "/dashboard"
                        ? pathname === item.href
                        : pathname.startsWith(item.href);
                    return (
                      <a
                        key={item.href}
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className={`flex items-center gap-2.5 px-2.5 h-9 rounded-lg text-[13px] ${
                          active
                            ? "bg-brand-tint text-brand-400 font-medium"
                            : "text-ink-soft hover:bg-hover hover:text-ink"
                        }`}
                      >
                        <Icon name={item.icon} className="h-4 w-4" />
                        {item.label}
                      </a>
                    );
                  })}
                </div>
              ))}
              <button
                onClick={handleLogout}
                className="flex items-center gap-2.5 px-2.5 h-9 rounded-lg text-[13px] text-ink-soft hover:bg-hover hover:text-danger"
              >
                <Icon name="logout" className="h-4 w-4" />
                {t("common.signOut")}
              </button>
            </nav>
          }
        />
      }
    >
      <ClientAuthGuard>{children}</ClientAuthGuard>
    </AppShell>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <LocaleProvider>
      <DashboardShell>{children}</DashboardShell>
    </LocaleProvider>
  );
}
