"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { isAuthenticated, getStoredUser, getMe, clearAuth } from "@/lib/auth";

const PUBLIC_ROUTES = ["/login", "/forbidden"];

/**
 * Strict owner-only gate (OQ-4). Enforces BOTH:
 *  1. Local storage owner session (`owner_at` / `owner_user`).
 *  2. Live `/auth/me` role claim — non-owner is denied regardless of what is
 *     stored locally. The backend `require_permission` remains the
 *     authoritative enforcement point; this component guards the portal UX.
 */
export default function OwnerAuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const redirecting = useRef(false);
  const [verified, setVerified] = useState<boolean>(false);

  useEffect(() => {
    const ok = isAuthenticated();
    if (!ok && !PUBLIC_ROUTES.includes(pathname) && !redirecting.current) {
      redirecting.current = true;
      router.replace("/login");
      return;
    }

    if (ok) {
      const user = getStoredUser();
      // Coarse local check first — deny immediately when role is known non-owner.
      if (user && user.role && user.role !== "owner") {
        clearAuth();
        if (!redirecting.current) {
          redirecting.current = true;
          router.replace("/forbidden");
        }
        return;
      }
      // Server-side role claim verification (defense in depth).
      getMe()
        .then((me) => {
          if (me.role !== "owner") {
            clearAuth();
            if (!redirecting.current) {
              redirecting.current = true;
              router.replace("/forbidden");
            }
            return;
          }
          setVerified(true);
        })
        .catch(() => {
          // Token expired beyond refresh — force login.
          if (!redirecting.current) {
            redirecting.current = true;
            router.replace("/login");
          }
        });
      return;
    }

    if (pathname === "/login") {
      setVerified(true);
    }
  }, [pathname, router]);

  // Authenticated owner reaches dashboard; public routes render immediately.
  if (pathname === "/login" || pathname === "/forbidden") return <>{children}</>;
  if (!isAuthenticated()) return <>{children}</>;
  if (!verified) return <>{children}</>;
  return <>{children}</>;
}
