import Sidebar from "@/components/layout/sidebar";
import Topbar from "@/components/layout/topbar";
import PermissionSync from "@/components/PermissionSync";
import { AppShell } from "@ds/components/AppShell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AppShell
      sidebar={<Sidebar />}
      topbar={
        <>
          <PermissionSync />
          <Topbar />
        </>
      }
    >
      {children}
    </AppShell>
  );
}
