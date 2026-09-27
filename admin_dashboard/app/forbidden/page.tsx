import Link from "next/link";

export default function ForbiddenPage() {
  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4">
      <div className="text-center">
        <div className="text-6xl font-bold text-danger mb-4 font-display">403</div>
        <h1 className="text-xl font-semibold text-ink mb-2">Access Denied</h1>
        <p className="text-ink-muted mb-6 text-sm">
          You do not have permission to access this section.
        </p>
        <Link
          href="/dashboard"
          className="inline-block px-4 py-2 rounded-lg bg-brand-500 text-ink-inverse text-sm font-medium hover:bg-brand-400 active:bg-brand-700 transition-colors"
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
