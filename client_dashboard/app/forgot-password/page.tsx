"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/auth";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Button, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setMessage("");
    setLoading(true);
    try {
      const res = await forgotPassword(email);
      setMessage(res.message);
    } catch {
      setMessage("If the email exists, a reset code has been sent.");
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
            <BrandLogo href="/forgot-password" variant="chip" height={30} />
            <div className="text-center">
              <p className="text-sm text-ink-soft">Reset Password</p>
              <p className="text-xs text-ink-muted mt-1">Enter your email to receive a reset code</p>
            </div>
          </div>

          {message ? (
            <div className="text-center flex flex-col items-center gap-2">
              <span className="h-12 w-12 rounded-xl bg-brand-tint text-brand-400 flex items-center justify-center mb-1">
                <Icon name="check-circle" className="h-6 w-6" />
              </span>
              <div className="text-sm text-ink-soft mb-3">{message}</div>
              <Link href="/login">
                <Button>Back to Login</Button>
              </Link>
              <Link href="/reset-password" className="text-sm text-ink-muted hover:text-ink">
                Already have a code? <span className="text-brand-400">Reset Password</span>
              </Link>
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
              <Button type="submit" disabled={loading} loading={loading} className="w-full" size="lg">
                Send Reset Code
              </Button>
            </form>
          )}

          {!message && (
            <div className="text-center mt-5">
              <Link href="/login" className="text-sm text-ink-muted hover:text-ink">
                Back to <span className="text-brand-400">Sign In</span>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
