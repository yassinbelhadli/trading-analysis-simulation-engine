"use client";

import { useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { isAuthenticated, getStoredUser } from "@/lib/auth";

const PUBLIC_ROUTES = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/forbidden",
];

export default function ClientAuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const redirecting = useRef(false);

  useEffect(() => {
    if (PUBLIC_ROUTES.includes(pathname)) return;

    const redirect = (to: string) => {
      if (!redirecting.current) {
        redirecting.current = true;
        router.replace(to);
      }
    };

    if (!isAuthenticated()) {
      redirect("/login");
      return;
    }

    const user = getStoredUser();
    // Role gate: a staff token must never render the client portal.
    if (user && user.role && user.role !== "client") {
      redirect("/forbidden");
      return;
    }
    if (user && user.email_verified === false) {
      redirect("/verify-email");
    }
  }, [pathname, router]);

  return <>{children}</>;
}
