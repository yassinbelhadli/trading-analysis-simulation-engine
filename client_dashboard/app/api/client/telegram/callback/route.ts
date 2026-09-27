/**
 * Telegram OIDC callback proxy route.
 *
 * Telegram redirects here after the user authorizes.
 * This route forwards the authorization code + state to the backend API,
 * which handles the actual token exchange, ID token validation, and
 * account linking. Then redirects the browser to the dashboard.
 */
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/**
 * Resolve the browser-facing origin for redirects.
 *
 * Priority:
 *   1. NEXT_PUBLIC_SITE_URL env var (set in production VPS)
 *   2. x-forwarded-host + x-forwarded-proto headers (set by Cloudflare tunnel / any reverse proxy)
 *   3. Fallback to request.url origin (local dev without tunnel)
 *
 * Never hardcodes a specific tunnel URL — works in dev, tunnel, and production.
 */
function resolveOrigin(request: NextRequest): string {
  // Production: explicit env var wins
  const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
  if (envUrl) {
    try { return new URL(envUrl).origin; } catch { /* fall through */ }
  }

  // Reverse proxy / Cloudflare tunnel: reconstruct from forwarded headers
  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedProto = request.headers.get("x-forwarded-proto");
  if (forwardedHost) {
    const proto = forwardedProto || "https";
    return `${proto}://${forwardedHost.split(",")[0].trim()}`;
  }

  // Local dev without tunnel: use request.url origin
  return new URL(request.url).origin;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");
  const reason = searchParams.get("reason");

  const origin = resolveOrigin(request);

  // If Telegram returned an error
  if (error) {
    return NextResponse.redirect(
      new URL(`/dashboard/telegram?telegram=error&reason=${error}`, origin),
    );
  }

  // If callback was redirected with explicit error from frontend logic
  if (reason) {
    return NextResponse.redirect(
      new URL(`/dashboard/telegram?telegram=error&reason=${reason}`, origin),
    );
  }

  if (!code || !state) {
    return NextResponse.redirect(
      new URL("/dashboard/telegram?telegram=error&reason=missing_params", origin),
    );
  }

  try {
    // Forward to backend API for token exchange + account linking
    const resp = await fetch(`${API_URL}/api/client/telegram/callback-exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state }),
    });

    const data = await resp.json();

    if (!resp.ok || !data.success) {
      const errReason = data.detail || "exchange_failed";
      return NextResponse.redirect(
        new URL(`/dashboard/telegram?telegram=error&reason=${encodeURIComponent(errReason)}`, origin),
      );
    }

    // Success — redirect to dashboard with connected status
    return NextResponse.redirect(
      new URL("/dashboard/telegram?telegram=connected", origin),
    );
  } catch (err) {
    return NextResponse.redirect(
      new URL("/dashboard/telegram?telegram=error&reason=network_error", origin),
    );
  }
}
