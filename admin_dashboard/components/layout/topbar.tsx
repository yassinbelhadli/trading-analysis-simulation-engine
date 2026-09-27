"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getStoredUser, logout, AuthUser } from "@/lib/auth";
import { getOverview, OverviewEngine } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { useAdminNavGroups } from "@/components/layout/sidebar";
import { AppTopbar } from "@ds/components/AppShell";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Icon } from "@ds/components/Icon";
import { Badge } from "@ds/components/ui";

const TITLES: Record<string, string> = {
  "/dashboard": "Overview",
  "/dashboard/clients": "Clients",
  "/dashboard/accounts": "MT5 Accounts",
  "/dashboard/licenses": "Licenses",
  "/dashboard/subscriptions": "Plans",
  "/dashboard/payments": "Payments",
  "/dashboard/promotions": "Promotions",
  "/dashboard/coupons": "Coupons",
  "/dashboard/trading": "Trading Overview",
  "/dashboard/trading/trades": "Active Trades",
  "/dashboard/trading/history": "Trade History",
  "/dashboard/trading/signals": "Signals",
  "/dashboard/trading/risk": "Risk Monitor",
  "/dashboard/trading/performance": "Performance",
  "/dashboard/trading/engine": "Trading Engine",
  "/dashboard/tickets": "Support Tickets",
  "/dashboard/ea-builds": "EA Builds",
  "/dashboard/telegram": "Telegram",
  "/dashboard/news": "News",
  "/dashboard/notifications": "Notifications",
  "/dashboard/system": "System Health",
  "/dashboard/audit": "Audit Logs",
  "/dashboard/roles": "Roles & Permissions",
  "/dashboard/users": "Users",
  "/dashboard/security": "Security",
  "/dashboard/settings": "Settings",
  "/dashboard/revenue": "Revenue",
};

export default function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const groups = useAdminNavGroups();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [engine, setEngine] = useState<OverviewEngine | null>(null);

  useEffect(() => {
    setUser(getStoredUser());
    const fetchEngine = () => {
      getOverview()
        .then((d) => setEngine(d.engine))
        .catch(() => {});
    };
    fetchEngine();
    const iv = setInterval(fetchEngine, 15000);
    return () => clearInterval(iv);
  }, []);

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const title =
    TITLES[pathname] ??
    (pathname.startsWith("/dashboard/trading/replay/")
      ? "Trade Replay"
      : pathname.startsWith("/dashboard/accounts/")
        ? "Account Detail"
        : pathname.startsWith("/dashboard/clients/")
          ? "Client Detail"
          : "Admin");

  const engineRunning = engine?.status?.toLowerCase() === "running";

  return (
    <AppTopbar
      title={title}
      left={<BrandLogo href="/dashboard" height={22} className="lg:hidden" />}
      right={
        <>
          {engine && (
            <Badge tone={engineRunning ? "green" : "red"} className="hidden sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              {engine.status}
              {engine.active_trades > 0 && ` · ${engine.active_trades} active`}
            </Badge>
          )}
          {user && (
            <div className="hidden md:flex items-center gap-2">
              <span className="text-[13px] text-ink-soft max-w-[140px] truncate">
                {user.first_name || user.email}
              </span>
              <Badge tone="blue">{user.role}</Badge>
            </div>
          )}
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
          {groups.map((g) => (
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
            Sign out
          </button>
        </nav>
      }
    />
  );
}
