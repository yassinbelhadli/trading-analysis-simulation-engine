"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login, verifyTwoFactor, TwoFactorRequired } from "@/lib/auth";
import { BrandLogo } from "@ds/components/BrandLogo";

export default function OwnerLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [code, setCode] = useState("");
  const [twoFactorStep, setTwoFactorStep] = useState<TwoFactorRequired | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const redirectOrDeny = (redirect_to: string | undefined) => {
    // Owner portal is strict owner-only (OQ-4). The stored user role is
    // checked here; the backend /auth/me + require_permission remain
    // authoritative. Non-owners never enter the dashboard.
    const user = JSON.parse(localStorage.getItem("owner_user") || "null");
    if (user && user.role === "owner") {
      router.replace("/dashboard");
    } else {
      router.replace("/forbidden");
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(email, password, rememberMe);
      if ("two_factor_required" in res) {
        setTwoFactorStep(res);
        return;
      }
      redirectOrDeny(res.redirect_to);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleTwoFactor = async (e: FormEvent) => {
    e.preventDefault();
    if (!twoFactorStep) return;
    setError("");
    setLoading(true);
    try {
      const res = await verifyTwoFactor(code, twoFactorStep.two_factor_token, rememberMe);
      redirectOrDeny(res.redirect_to);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  const backToCredentials = () => {
    setTwoFactorStep(null);
    setCode("");
    setError("");
  };

  const card =
    "w-full max-w-sm bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-6 shadow-lg shadow-black/5";

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className={card}>
          <div className="flex flex-col items-center mb-6 gap-3">
            <BrandLogo href="/login" variant="chip" height={28} />
            <div className="text-center">
              <p className="text-sm text-[var(--text-secondary)]">
                {twoFactorStep ? "Two-Factor Authentication" : "Owner Portal"}
              </p>
            </div>
          </div>

          {twoFactorStep ? (
            <form onSubmit={handleTwoFactor} className="flex flex-col gap-3.5">
              <div className="text-xs text-[var(--text-secondary)] text-center">
                Enter the 6-digit code from your authenticator app.
              </div>
              <div>
                <label htmlFor="code" className="text-xs text-[var(--text-secondary)] block mb-1">
                  Authentication Code
                </label>
                <input
                  id="code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  required
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-center text-lg tracking-[0.3em] text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent)]"
                  placeholder="000000"
                />
              </div>

              {error && (
                <div className="text-sm text-red-400 text-center">{error}</div>
              )}

              <button
                type="submit"
                disabled={loading || code.length < 6}
                className="w-full py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
              >
                {loading ? "Verifying..." : "Verify & Sign In"}
              </button>

              <button
                type="button"
                onClick={backToCredentials}
                className="w-full py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
              >
                ← Back to login
              </button>
            </form>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
              <div>
                <label htmlFor="email" className="text-xs text-[var(--text-secondary)] block mb-1">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent)]"
                  placeholder="owner@ictfundedeapro.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="text-xs text-[var(--text-secondary)] block mb-1">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border)] text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent)]"
                  placeholder="••••••••"
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer text-xs text-[var(--text-secondary)]">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="accent-[var(--accent)]"
                  />
                  Remember me
                </label>
              </div>

              {error && (
                <div className="text-sm text-red-400 text-center">{error}</div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
              >
                {loading ? "Signing in..." : "Sign In"}
              </button>
            </form>
          )}
        </div>

        <div className="text-center mt-4">
          <span className="text-xs text-[var(--text-secondary)]">ICT Funded EA Pro · Owner Control Plane</span>
        </div>
      </div>
    </div>
  );
}
