export type NoticeState = { ok: boolean; text: string } | null;

export function Notice({ state }: { state: NoticeState }) {
  if (!state) return null;
  return (
    <div
      className={`text-sm px-3 py-2 rounded-lg border ${
        state.ok
          ? "text-[var(--success)] border-[var(--success)]/30 bg-[var(--success)]/10"
          : "text-red-400 border-red-500/30 bg-red-500/10"
      }`}
    >
      {state.text}
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div>
      <h1 className="page-title">{title}</h1>
      {subtitle && <p className="text-sm text-[var(--text-secondary)] -mt-2">{subtitle}</p>}
    </div>
  );
}

export function EmptyState({ icon, title, subtitle, action }: {
  icon: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="card text-center py-12">
      <div className="text-4xl mb-3">{icon}</div>
      <div className="text-[var(--text-secondary)] mb-1">{title}</div>
      {subtitle && <div className="text-sm text-[var(--text-secondary)]">{subtitle}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function StatCard({ label, value, color = "default" }: {
  label: string;
  value: string | number;
  color?: "success" | "error" | "warning" | "default";
}) {
  const colors: Record<string, string> = {
    success: "text-[var(--success)]",
    error: "text-[var(--error)]",
    warning: "text-[var(--warning)]",
    default: "text-[var(--text-primary)]",
  };
  return (
    <div className="card">
      <div className="text-xs text-[var(--text-secondary)] mb-1">{label}</div>
      <div className={`text-xl font-bold ${colors[color]}`}>{value}</div>
    </div>
  );
}

export function InfoRow({ k, v, color }: {
  k: string;
  v: string | number | React.ReactNode;
  color?: "success" | "error" | "warning";
}) {
  const cls =
    color === "success"
      ? "text-[var(--success)]"
      : color === "error"
        ? "text-[var(--error)]"
        : color === "warning"
          ? "text-[var(--warning)]"
          : "text-[var(--text-primary)]";
  return (
    <div className="flex justify-between border-b border-[var(--border)] py-1.5">
      <span className="text-[var(--text-secondary)]">{k}</span>
      <span className={`font-medium ${cls}`}>{v}</span>
    </div>
  );
}

export function Dot({ on }: { on: boolean }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${on ? "bg-[var(--success)]" : "bg-[var(--error)]"}`} />
  );
}

export function StatusBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
        active ? "bg-[var(--success)]/15 text-[var(--success)]" : "bg-[var(--error)]/15 text-[var(--error)]"
      }`}
    >
      {label}
    </span>
  );
}

export function Loading({ text = "Loading..." }: { text?: string }) {
  return <div className="text-[var(--text-secondary)] text-center py-20">{text}</div>;
}

export function ErrorBox({ text }: { text: string }) {
  return <div className="text-red-400 text-center py-20">{text}</div>;
}
