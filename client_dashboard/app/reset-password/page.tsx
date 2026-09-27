"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { resetPassword } from "@/lib/auth";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Button, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      const res = await resetPassword(email, code, password);
      setSuccess(res.message);
      setTimeout(() => router.push("/login"), 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
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
            <BrandLogo href="/reset-password" variant="chip" height={30} />
            <div className="text-center">
              <p className="text-sm text-ink-soft">Reset Password</p>
              <p className="text-xs text-ink-muted mt-1">Enter the code from your email</p>
            </div>
          </div>

          {success ? (
            <div className="text-center flex flex-col items-center gap-2">
              <span className="h-12 w-12 rounded-xl bg-brand-tint text-brand-400 flex items-center justify-center mb-1">
                <Icon name="check-circle" className="h-6 w-6" />
              </span>
              <div className="text-sm text-ink-soft">{success}</div>
              <p className="text-xs text-ink-muted">Redirecting to login...</p>
            </div>
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
                label="Reset Code"
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                required
                placeholder="e.g. AB12CD34"
                className="[&_input]:text-center [&_input]:font-mono [&_input]:tracking-widest"
              />
              <TextField
                label="New Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                placeholder="Min 8 characters"
                icon="lock"
              />
              {error && (
                <div className="flex items-center gap-2 text-sm text-danger">
                  <Icon name="x-circle" className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}
              <Button type="submit" disabled={loading} loading={loading} className="w-full" size="lg">
                Reset Password
              </Button>
            </form>
          )}

          {!success && (
            <div className="text-center mt-5">
              <Link href="/login" className="text-sm text-brand-400 hover:text-brand-300">Back to Sign In</Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
