"use client";

import Link from "next/link";
import { clearAuth } from "@/lib/auth";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Button } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

export default function ForbiddenPage() {
  const handleReset = () => {
    clearAuth();
    window.location.href = "/login";
  };

  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4 relative overflow-hidden">
      {/* subtle brand glow */}
      <div
        aria-hidden
        className="absolute -top-32 left-1/2 -translate-x-1/2 h-64 w-[42rem] rounded-full blur-3xl opacity-20 pointer-events-none"
        style={{ background: "radial-gradient(closest-side, #12b76a, transparent)" }}
      />
      <div className="w-full max-w-sm relative">
        <div className="bg-raised border border-line rounded-xl p-8 shadow-lift text-center">
          <div className="flex flex-col items-center mb-6 gap-4">
            <BrandLogo href="/forbidden" variant="chip" height={30} />
            <span className="h-14 w-14 rounded-xl bg-danger/10 text-danger flex items-center justify-center">
              <Icon name="lock" className="h-7 w-7" />
            </span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight mb-2">Access Restricted</h1>
          <p className="text-sm text-ink-muted mb-6">
            This portal is for client accounts only. Staff and admin accounts cannot access the Client Portal.
          </p>
          <div className="flex flex-col gap-2">
            <Button className="w-full" icon="logout" onClick={handleReset}>
              Sign out and return to login
            </Button>
            <Link href="https://ictfundedeapro.com" className="text-sm text-brand-400 hover:text-brand-300">
              Visit the website
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
