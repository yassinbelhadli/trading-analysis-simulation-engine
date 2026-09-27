"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AppTopbar } from "@ds/components/AppShell";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Icon } from "@ds/components/Icon";
import { Button } from "@ds/components/ui";
import { getStoredUser, logout, AuthUser } from "@/lib/auth";
import { getOverview, OverviewEngine } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { OWNER_NAV_GROUPS } from "@/components/layout/sidebar";

const TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/dashboard/revenue": "Revenue",
  "/dashboard/billing": "Billing",
  "/dashboard/promotions": "Promotions",
  "/dashboard/users": "Users",
  "/dashboard/roles": "Roles & Permissions",
  "/dashboard/audit": "Audit Logs",
  "/dashboard/engine": "Engine Control",
  "/dashboard/system": "System Health",
  "/dashboard/system/integrations": "Integrations",
  "/dashboard/settings": "Safe Settings",
  "/dashboard/settings/secrets": "Secrets",
  "/dashboard/news": "News",
  "/dashboard/alerts": "Alerts",
};

export default function OwnerTopbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [engine, setEngine] = useState<OverviewEngine | null>(null);

  useEffect(() => {
    setUser(getStoredUser());
    const fetch = () => {
      getOverview()
        .then((d) => setEngine(d.engine))
        .catch(() => {});
    };
    fetch();
    const iv = setInterval(fetch, 15000);
    return () => clearInterval(iv);
  }, []);

  const handleLogout = async () => {
    await logout();
    router.replace("/login");
  };

  const currentTitle = TITLES[pathname] ?? "Owner Portal";
  const running = engine?.status?.toLowerCase() === "running";

  return (
    <AppTopbar
      title={currentTitle}
      left={<BrandLogo href="/dashboard" height={22} className="lg:hidden" />}
      right={
        <>
          {engine && (
            <span className="hidden sm:flex items-center gap-1.5 text-xs font-mono text-ink-soft">
              <span className={`h-1.5 w-1.5 rounded-full ${running ? "bg-ok" : "bg-danger"}`} />
              Engine {engine.status}
              {engine.pid != null && <span className="text-ink-muted">PID {engine.pid}</span>}
              {engine.active_trades != null && (
                <span className="text-ink-muted">· {engine.active_trades} active</span>
              )}
            </span>
          )}
          {user && (
            <span className="hidden md:inline-flex items-center rounded-full border border-brand-500/30 bg-brand-tint px-2.5 py-0.5 text-[11px] font-medium text-brand-400">
              Owner
            </span>
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
          {OWNER_NAV_GROUPS.map((g) => (
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
            Sign out
          </button>
        </nav>
      }
    />
  );
}
