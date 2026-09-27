"use client";

import Link from "next/link";
import PermissionGuard from "@/components/auth/permission_guard";
import { Button, EmptyState, PageHeader } from "@ds/components/ui";

export default function MT5AccountDetailPage() {
  return (
    <PermissionGuard permission="accounts.read">
      <div>
        <PageHeader title="MT5 Account Details" subtitle="Individual client account view." />
        <EmptyState
          variant="gap"
          icon="server"
          title="MT5 Account Details — Not available"
          description="Individual MT5 account management requires backend integration and is not part of the current API contract."
        />
        <div className="flex justify-center mt-4">
          <Link href="/dashboard/accounts">
            <Button variant="secondary" icon="arrow-left">
              Back to MT5 Accounts
            </Button>
          </Link>
        </div>
      </div>
    </PermissionGuard>
  );
}
