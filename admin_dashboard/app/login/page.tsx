"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { login, verifyTwoFactor, TwoFactorRequired } from "@/lib/auth";
import { BrandLogo } from "@ds/components/BrandLogo";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [code, setCode] = useState("");
  const [twoFactorStep, setTwoFactorStep] = useState<TwoFactorRequired | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
      router.replace(res.redirect_to || "/dashboard");
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
      router.replace(res.redirect_to || "/dashboard");
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
    "w-full max-w-sm bg-raised border border-line rounded-xl p-6 shadow-lg shadow-black/5";

  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className={card}>
          <div className="flex flex-col items-center mb-6 gap-3">
            <BrandLogo href="/login" variant="chip" height={28} />
            <div className="text-center">
              <p className="text-sm text-ink-soft">
                {twoFactorStep ? "Two-Factor Authentication" : "Admin Dashboard"}
              </p>
            </div>
          </div>

          {twoFactorStep ? (
            <form onSubmit={handleTwoFactor} className="flex flex-col gap-3.5">
              <div className="text-xs text-ink-muted text-center">
                Enter the 6-digit code from your authenticator app.
              </div>
              <div>
                <label htmlFor="code" className="text-xs font-medium text-ink-soft block mb-1.5">
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
                  className="w-full h-9 px-3 rounded-lg bg-input border border-line text-center text-lg tracking-[0.3em] text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
                  placeholder="000000"
                />
              </div>

              {error && (
                <div className="text-sm text-danger text-center">{error}</div>
              )}

              <button
                type="submit"
                disabled={loading || code.length < 6}
                className="w-full h-10 rounded-lg bg-brand-500 text-ink-inverse text-sm font-medium hover:bg-brand-400 active:bg-brand-700 transition-colors disabled:opacity-50"
              >
                {loading ? "Verifying..." : "Verify & Sign In"}
              </button>

              <button
                type="button"
                onClick={backToCredentials}
                className="w-full py-1 text-xs text-ink-muted hover:text-ink transition-colors"
              >
                Back to login
              </button>
            </form>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3.5">
              <div>
                <label htmlFor="email" className="text-xs font-medium text-ink-soft block mb-1.5">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
                  placeholder="admin@example.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="text-xs font-medium text-ink-soft block mb-1.5">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
                  placeholder="••••••••"
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 cursor-pointer text-xs text-ink-soft">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="accent-brand-500"
                  />
                  Remember me
                </label>
              </div>

              {error && (
                <div className="text-sm text-danger text-center">{error}</div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full h-10 rounded-lg bg-brand-500 text-ink-inverse text-sm font-medium hover:bg-brand-400 active:bg-brand-700 transition-colors disabled:opacity-50"
              >
                {loading ? "Signing in..." : "Sign In"}
              </button>
            </form>
          )}
        </div>

        <div className="text-center mt-4">
          <span className="text-xs text-ink-muted">ICT Funded EA Pro · v1.0</span>
        </div>
      </div>
    </div>
  );
}
