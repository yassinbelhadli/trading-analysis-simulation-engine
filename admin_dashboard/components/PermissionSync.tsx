"use client";

import { useEffect } from "react";
import { getMe, savePermissions, getPermissions } from "@/lib/auth";

/**
 * Syncs permissions from the backend /auth/me endpoint into localStorage.
 * This ensures permissions are available after page refresh, even if the user
 * logged in before the RBAC system was deployed.
 *
 * Runs once on mount. If permissions are already stored and match, no write.
 */
export default function PermissionSync() {
  useEffect(() => {
    // Skip if no token (not logged in)
    try {
      const stored = localStorage.getItem("admin_at");
      if (!stored) return;

      getMe()
        .then((me) => {
          if (me.permissions && me.permissions.length > 0) {
            const current = getPermissions();
            // Only write if permissions actually changed (avoid unnecessary re-renders)
            if (JSON.stringify(current) !== JSON.stringify(me.permissions)) {
              savePermissions(me.permissions);
              // Force sidebar re-render by dispatching a custom event
              window.dispatchEvent(new Event("permissions-synced"));
            }
          }
        })
        .catch(() => {
          // Silently ignore — will be caught by auth guard
        });
    } catch {
      // SSR or no window
    }
  }, []);

  return null;
}
