import { memo } from "react";
import { StatCard as DSStatCard, type StatTone } from "@ds/components/ui";

type Color = "default" | "success" | "warning" | "error";

const TONE_MAP: Record<Color, StatTone> = {
  default: "default",
  success: "green",
  warning: "amber",
  error: "red",
};

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: Color;
}

function StatCard({ label, value, sub, color = "default" }: StatCardProps) {
  return <DSStatCard label={label} value={value} sub={sub} tone={TONE_MAP[color]} />;
}

export default memo(StatCard);
