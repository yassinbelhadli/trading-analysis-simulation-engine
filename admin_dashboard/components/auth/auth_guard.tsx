"use client";

import { useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";

const PUBLIC_ROUTES = ["/login", "/forbidden"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const redirecting = useRef(false);

  useEffect(() => {
    const ok = isAuthenticated();
    if (!ok && !PUBLIC_ROUTES.includes(pathname) && !redirecting.current) {
      redirecting.current = true;
      router.replace("/login");
    }
    if (ok && pathname === "/login") {
      router.replace("/dashboard");
    }
  }, [pathname, router]);

  return <>{children}</>;
}
