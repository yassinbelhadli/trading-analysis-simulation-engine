import { StatusPill, type Status } from "@ds/components/ui";

interface StatusBadgeProps {
  status: string;
}

const STATUS_MAP: Record<string, Status> = {
  HEALTHY: "active",
  RUNNING: "active",
  ACTIVE: "active",
  SUCCESS: "active",
  WARNING: "warning",
  PAUSED: "warning",
  PENDING: "pending",
  PROCESSING: "pending",
  ERROR: "error",
  DISABLED: "error",
  FAILED: "error",
  EXPIRED: "error",
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const pill = STATUS_MAP[status] ?? "inactive";
  return <StatusPill status={pill}>{status}</StatusPill>;
}
