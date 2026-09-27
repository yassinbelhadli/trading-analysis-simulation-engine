"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login, verify2FA } from "@/lib/auth";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Button, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [twoFactorToken, setTwoFactorToken] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(email, password);
      if ("two_factor_required" in res) {
        setTwoFactorToken(res.two_factor_token);
      } else {
        router.replace("/dashboard");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    if (!twoFactorToken) return;
    setError("");
    setLoading(true);
    try {
      await verify2FA(twoFactorToken, code);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4 relative overflow-hidden">
      {/* subtle brand glow */}
      <div
        aria-hidden
        className="absolute -top-32 left-1/2 -translate-x-1/2 h-64 w-[42rem] rounded-full blur-3xl opacity-20 pointer-events-none"
        style={{ background: "radial-gradient(closest-side, #12b76a, transparent)" }}
      />
      <div className="w-full max-w-sm relative">
        <div className="bg-raised border border-line rounded-xl p-8 shadow-lift">
          <div className="flex flex-col items-center mb-8 gap-4">
            <BrandLogo href="/login" variant="chip" height={30} />
            <div className="text-center">
              <p className="text-sm text-ink-soft">Client Portal</p>
              <p className="text-xs text-ink-muted mt-1">Secure sign in</p>
            </div>
          </div>

          {twoFactorToken ? (
            <form onSubmit={handleVerify} className="flex flex-col gap-4">
              <TextField
                label="Two-Factor Authentication Code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                autoFocus
                placeholder="000000"
                maxLength={6}
                hint="Enter the 6-digit code from your authenticator app."
                className="[&_input]:text-center [&_input]:font-mono [&_input]:text-lg [&_input]:tracking-widest"
              />
              {error && (
                <div className="flex items-center gap-2 text-sm text-danger">
                  <Icon name="x-circle" className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}
              <Button type="submit" disabled={loading || code.length !== 6} loading={loading} className="w-full" size="lg">
                Verify & Sign In
              </Button>
              <button
                type="button"
                onClick={() => setTwoFactorToken(null)}
                className="w-full text-center text-xs text-ink-muted hover:text-ink"
              >
                Use a different account
              </button>
            </form>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="client@example.com"
                icon="mail"
              />
              <TextField
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                icon="lock"
              />
              {error && (
                <div className="flex items-center gap-2 text-sm text-danger">
                  <Icon name="x-circle" className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}
              <Button type="submit" disabled={loading} loading={loading} className="w-full" size="lg">
                Sign In
              </Button>
            </form>
          )}

          {!twoFactorToken && (
            <div className="flex flex-col items-center gap-2 mt-5 text-sm">
              <Link href="/forgot-password" className="text-brand-400 hover:text-brand-300">
                Forgot password?
              </Link>
              <Link href="/register" className="text-ink-muted hover:text-ink">
                Don&apos;t have an account?{" "}
                <span className="text-brand-400">Register</span>
              </Link>
            </div>
          )}
        </div>
        <p className="text-center mt-5 text-xs text-ink-muted">
          Protected by ICT Funded EA Pro license & risk systems
        </p>
      </div>
    </div>
  );
}
