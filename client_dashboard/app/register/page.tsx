"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { register } from "@/lib/auth";
import { useTheme } from "@/components/ThemeProvider";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Button, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

export default function RegisterPage() {
  const { brandName } = useTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);
    try {
      const res = await register({ email, password, first_name: firstName, last_name: lastName });
      if (res.verification_sent) {
        setSuccess("Registration successful. We sent a verification code to your email.");
      } else {
        setSuccess(
          "Registration successful, but we could not send the verification email right now. " +
          "Please contact support to complete verification.",
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
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
            <BrandLogo href="/register" variant="chip" height={30} />
            <div className="text-center">
              <p className="text-sm text-ink-soft">{brandName} Client Portal</p>
              <p className="text-xs text-ink-muted mt-1">Create your account</p>
            </div>
          </div>

          {success ? (
            <div className="text-center flex flex-col items-center gap-2">
              <span className="h-12 w-12 rounded-xl bg-brand-tint text-brand-400 flex items-center justify-center mb-1">
                <Icon name="check-circle" className="h-6 w-6" />
              </span>
              <div className="text-sm text-ink-soft mb-3">{success}</div>
              <Link href="/verify-email">
                <Button icon="check">Verify Email</Button>
              </Link>
              <Link href="/login" className="text-sm text-ink-muted hover:text-ink">
                Back to <span className="text-brand-400">Sign In</span>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  label="First Name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                />
                <TextField
                  label="Last Name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                />
              </div>
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
                Create Account
              </Button>
            </form>
          )}

          {!success && (
            <div className="text-center mt-5">
              <Link href="/login" className="text-sm text-ink-muted hover:text-ink">
                Already have an account? <span className="text-brand-400">Sign In</span>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
