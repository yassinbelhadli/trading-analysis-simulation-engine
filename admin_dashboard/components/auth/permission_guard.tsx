"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser, getPermissions } from "@/lib/auth";
import { checkPermission } from "@/lib/api";

interface Props {
  permission?: string;
  roles?: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

function AccessDenied() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="text-lg font-semibold text-ink">Access Denied</div>
        <div className="text-sm mt-1 text-ink-muted">
          You do not have permission to access this section.
        </div>
      </div>
    </div>
  );
}

export default function PermissionGuard({ permission, roles, children, fallback }: Props) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!mounted) return;
    let cancelled = false;
    (async () => {
      const user = getStoredUser();
      if (!user) { router.push("/login"); return; }
      if (user.role === "owner") { setAllowed(true); return; }
      if (!permission && !roles) { setAllowed(true); return; }
      if (roles && !roles.includes(user.role || "")) {
        setAllowed(false);
        return;
      }
      if (permission) {
        const perms = getPermissions();
        if (perms.includes("*") || perms.includes(permission)) {
          setAllowed(true);
          return;
        }
        const dot = permission.indexOf(".");
        const resource = dot === -1 ? permission : permission.slice(0, dot);
        const action = dot === -1 ? "read" : permission.slice(dot + 1);
        const ok = await checkPermission(resource, action);
        if (cancelled) return;
        setAllowed(ok);
        return;
      }
      setAllowed(true);
    })();
    return () => { cancelled = true; };
  }, [mounted, permission, roles, router]);

  // While loading, show nothing — prevents protected API calls before permission check
  if (!mounted || allowed === null) return <div className="text-ink-muted text-center py-20">Checking permissions...</div>;
  if (allowed === false && fallback !== undefined) return <>{fallback}</>;
  if (allowed === false) return <AccessDenied />;
  return <>{children}</>;
}
