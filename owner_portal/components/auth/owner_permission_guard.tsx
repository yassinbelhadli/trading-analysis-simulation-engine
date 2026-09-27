"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getStoredUser } from "@/lib/auth";
import { checkPermission } from "@/lib/api";

interface Props {
  permission?: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * Coarse frontend gate for the Owner Portal. The backend `require_permission`
 * is the authoritative enforcement point (owner wildcard `"*"` passes every
 * frozen endpoint; 403 on any bypass). This component only guards UX and
 * short-circuits for the owner role — the only role this portal serves.
 */
export default function OwnerPermissionGuard({ permission, children, fallback }: Props) {
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
      if (!permission) { setAllowed(true); return; }
      const dot = permission.indexOf(".");
      const resource = dot === -1 ? permission : permission.slice(0, dot);
      const action = dot === -1 ? "read" : permission.slice(dot + 1);
      const ok = await checkPermission(resource, action);
      if (cancelled) return;
      if (!ok && fallback === undefined) { router.push("/forbidden"); return; }
      setAllowed(ok);
      return;
    })();
    return () => { cancelled = true; };
  }, [mounted, permission, router, fallback]);

  if (!mounted || allowed === null) return <>{children}</>;
  if (allowed === false && fallback !== undefined) return <>{fallback}</>;
  if (allowed === false) return null;
  return <>{children}</>;
}
