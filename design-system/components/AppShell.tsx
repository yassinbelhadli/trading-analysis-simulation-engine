"use client";

import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Icon, type IconName } from "./Icon";
import { BrandLogo } from "./BrandLogo";

/* ==========================================================================
   Design System V2 — App shell (Sidebar + Topbar)
   Grouped sidebar with collapse, active-path highlighting, topbar with
   mobile drawer. Portals pass their own nav groups + topbar actions.
   ========================================================================== */

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  badge?: string | number;
  /** Exact match instead of prefix match (e.g. index routes). */
  exact?: boolean;
  /** Hidden entirely (RBAC-filtered by the caller). */
  hide?: boolean;
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
}

export interface AppSidebarProps {
  groups: NavGroup[];
  footer?: ReactNode;
  logoHref?: string;
}

export function AppSidebar({ groups, footer, logoHref = "/dashboard" }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex flex-col w-[240px] shrink-0 bg-raised border-r border-line h-[100dvh] sticky top-0">
      <div className="flex items-center h-[68px] px-4 border-b border-line">
        <BrandLogo href={logoHref} height={26} />
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
        {groups.map((group, gi) => (
          <div key={gi}>
            {group.label && (
              <p className="px-2 mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                {group.label}
              </p>
            )}
            <ul className="space-y-0.5">
              {group.items
                .filter((it) => !it.hide)
                .map((item) => {
                  const active = item.exact
                    ? pathname === item.href
                    : pathname === item.href || pathname.startsWith(item.href + "/") || (item.href === "/dashboard" && pathname === "/dashboard");
                  return (
                    <li key={item.href}>
                      <a
                        href={item.href}
                        className={`flex items-center gap-2.5 rounded-lg px-2.5 h-9 text-[13px] transition-colors ${
                          active
                            ? "bg-brand-tint text-brand-400 font-medium"
                            : "text-ink-soft hover:bg-hover hover:text-ink"
                        }`}
                      >
                        <Icon name={item.icon} className="h-4 w-4 shrink-0" />
                        <span className="flex-1 truncate">{item.label}</span>
                        {item.badge !== undefined && (
                          <span className="rounded-full bg-hover border border-line px-1.5 py-px text-[10px] font-mono text-ink-soft">
                            {item.badge}
                          </span>
                        )}
                      </a>
                    </li>
                  );
                })}
            </ul>
          </div>
        ))}
      </nav>
      {footer && <div className="border-t border-line p-3">{footer}</div>}
    </aside>
  );
}

export interface AppTopbarProps {
  title?: string;
  breadcrumb?: ReactNode;
  left?: ReactNode;
  right?: ReactNode;
  /** Rendered below the topbar on mobile (drawer with nav groups). */
  mobileNav?: ReactNode;
}

export function AppTopbar({ title, breadcrumb, left, right, mobileNav }: AppTopbarProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <header className="sticky top-0 z-40 h-[56px] flex items-center justify-between gap-3 px-4 sm:px-6 bg-base/85 backdrop-blur-md border-b border-line">
        <div className="flex items-center gap-3 min-w-0">
          {mobileNav && (
            <button
              onClick={() => setOpen((v) => !v)}
              aria-label="Toggle navigation"
              className="lg:hidden h-8 w-8 rounded-md flex items-center justify-center text-ink-soft hover:bg-hover hover:text-ink"
            >
              <Icon name={open ? "close" : "menu"} className="h-4.5 w-4.5" />
            </button>
          )}
          {left}
          <div className="min-w-0">
            {breadcrumb}
            {title && <h1 className="text-sm font-semibold truncate leading-5">{title}</h1>}
          </div>
        </div>
        {right && <div className="flex items-center gap-2 shrink-0">{right}</div>}
      </header>
      {open && mobileNav && (
        <div className="lg:hidden fixed inset-x-0 top-[56px] bottom-0 z-30 bg-base overflow-y-auto px-4 py-4 border-b border-line">
          {mobileNav}
        </div>
      )}
    </>
  );
}

export interface ShellProps {
  sidebar: ReactNode;
  topbar?: ReactNode;
  children: ReactNode;
}

/** Two-column fixed app shell: sidebar + scrollable content column. */
export function AppShell({ sidebar, topbar, children }: ShellProps) {
  return (
    <div className="min-h-[100dvh] bg-base text-ink">
      <div className="flex">
        {sidebar}
        <div className="flex-1 min-w-0 flex flex-col">
          {topbar}
          <main className="flex-1 p-4 sm:p-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
