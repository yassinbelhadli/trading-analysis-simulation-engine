"use client";

import { Suspense, useState, FormEvent, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { BrandLogo } from "@ds/components/BrandLogo";
import { Button, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

function VerifyForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    const urlCode = searchParams.get("code");
    if (urlCode) setCode(urlCode.toUpperCase());
  }, [searchParams]);

  const handleVerify = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    try {
      const res = await fetch("/_api/auth/verify-email/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Verification failed");
      setMessage(data.message);
      setTimeout(() => router.push("/login"), 1500);
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
            <BrandLogo href="/verify-email" variant="chip" height={30} />
            <div className="text-center">
              <p className="text-sm text-ink-soft">Verify Email</p>
              <p className="text-xs text-ink-muted mt-1">Enter the verification code sent to your email</p>
            </div>
          </div>

          {message ? (
            <div className="text-center flex flex-col items-center gap-2">
              <span className="h-12 w-12 rounded-xl bg-brand-tint text-brand-400 flex items-center justify-center mb-1">
                <Icon name="check-circle" className="h-6 w-6" />
              </span>
              <div className="text-sm text-ink-soft mb-3">{message}</div>
              <Link href="/login">
                <Button>Go to Login</Button>
              </Link>
            </div>
          ) : (
            <>
              <form onSubmit={handleVerify} className="flex flex-col gap-4">
                <TextField
                  label="Verification Code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  required
                  placeholder="XXXXXXXX"
                  maxLength={8}
                  className="[&_input]:text-center [&_input]:font-mono [&_input]:text-lg [&_input]:tracking-widest"
                />
                {error && (
                  <div className="flex items-center gap-2 text-sm text-danger">
                    <Icon name="x-circle" className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}
                <Button type="submit" disabled={loading} loading={loading} className="w-full" size="lg">
                  Verify Email
                </Button>
              </form>
              <div className="text-center mt-5">
                <Link href="/login" className="text-sm text-brand-400 hover:text-brand-300">Back to Login</Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-base flex items-center justify-center">
          <div className="text-sm text-ink-muted">Loading...</div>
        </div>
      }
    >
      <VerifyForm />
    </Suspense>
  );
}
