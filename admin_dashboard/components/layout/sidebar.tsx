"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { logout, getPermissions } from "@/lib/auth";
import { getFilteredGroups } from "@/lib/permissions";
import { useTheme } from "@/components/ThemeProvider";
import { AppSidebar, type NavGroup } from "@ds/components/AppShell";
import { Icon, type IconName } from "@ds/components/Icon";
import { Button } from "@ds/components/ui";

/** Role-filtered nav groups backed by lib/permissions (RBAC mirror, not enforcement). */
export function useAdminNavGroups(): NavGroup[] {
  const [groups, setGroups] = useState<NavGroup[]>([]);

  const loadPermissions = () => {
    const perms = getPermissions();
    setGroups(
      getFilteredGroups(perms).map((g) => ({
        label: g.label,
        items: g.items.map((item) => ({
          href: item.href,
          label: item.label,
          icon: item.icon as IconName,
        })),
      }))
    );
  };

  useEffect(() => {
    loadPermissions();
    // Re-read permissions when PermissionSync fetches them from /auth/me
    const onSync = () => loadPermissions();
    window.addEventListener("permissions-synced", onSync);
    return () => window.removeEventListener("permissions-synced", onSync);
  }, []);

  return groups;
}

export default function Sidebar() {
  const router = useRouter();
  const { theme, toggle } = useTheme();
  const groups = useAdminNavGroups();

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
