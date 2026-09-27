import Link from "next/link";

export default function ForbiddenPage() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4">
      <div className="text-center">
        <div className="text-6xl font-bold text-[var(--error)] mb-4">403</div>
        <h1 className="text-xl font-semibold mb-2">Access Denied</h1>
        <p className="text-[var(--text-secondary)] mb-6 text-sm">
          This portal is restricted to the platform owner.
        </p>
        <Link
          href="/login"
          className="inline-block px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm hover:bg-[var(--accent-hover)] transition-colors"
        >
          Go to Login
        </Link>
      </div>
    </div>
  );
}
