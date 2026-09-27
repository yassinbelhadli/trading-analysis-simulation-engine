"use client";

import OwnerSidebar from "@/components/layout/sidebar";
import OwnerTopbar from "@/components/layout/topbar";
import { AppShell } from "@ds/components/AppShell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell sidebar={<OwnerSidebar />} topbar={<OwnerTopbar />}>
      {children}
    </AppShell>
  );
}
