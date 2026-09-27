"use client";

export interface AuthUser {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  role: string | null;
  email_verified: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  remember_me?: boolean;
  user: AuthUser;
  redirect_to: string;
}

export interface TwoFactorRequired {
  two_factor_required: true;
  two_factor_token: string;
  expires_in: number;
  email: string;
  redirect_to: string;
}

export interface MeResponse {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  role: string | null;
  two_factor_enabled: boolean;
  two_factor_pending: boolean;
  active_sessions: number;
}

// Owner Portal storage keys — kept separate from admin portal keys
// (owner_at/owner_rt/owner_user vs admin_at/admin_rt/admin_user).
// Isolation between the two portals relies on distinct origins + these
// distinct keys; they never read each other's localStorage.
const TOKEN_KEY = "owner_at";
const REFRESH_KEY = "owner_rt";
const USER_KEY = "owner_user";

export function saveAuth(data: LoginResponse): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(REFRESH_KEY, data.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

export async function login(
  email: string,
  password: string,
  rememberMe = false,
): Promise<LoginResponse | TwoFactorRequired> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, remember_me: rememberMe }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Login failed");
  }
  const data: LoginResponse | TwoFactorRequired = await res.json();
  if ("two_factor_required" in data) return data;
  saveAuth(data as LoginResponse);
  return data;
}

export async function verifyTwoFactor(
  code: string,
  twoFactorToken: string,
  rememberMe = false,
): Promise<LoginResponse> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const res = await fetch(`${API}/auth/2fa/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, two_factor_token: twoFactorToken, remember_me: rememberMe }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Two-factor verification failed");
  }
  const data: LoginResponse = await res.json();
  saveAuth(data);
  return data;
}

export async function getMe(): Promise<MeResponse> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = getAccessToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(`${API}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401 && (await refreshAccessToken())) {
    return getMe();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Failed to load account");
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Singleton refresh mutex — prevents concurrent refreshAccessToken() calls
// from racing and consuming the same refresh token twice (invalid_grant).
// When multiple requests hit 401 simultaneously, only one refresh is made;
// the others wait for and reuse its result.
// ---------------------------------------------------------------------------
let _refreshInFlight: Promise<string | null> | null = null;

export async function refreshAccessToken(): Promise<string | null> {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = _doRefresh();
  try {
    return await _refreshInFlight;
  } finally {
    _refreshInFlight = null;
  }
}

async function _doRefresh(): Promise<string | null> {
  const rt = getRefreshToken();
  if (!rt) return null;
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  try {
    const res = await fetch(`${API}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) {
      clearAuth();
      return null;
    }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);
    return data.access_token;
  } catch {
    clearAuth();
    return null;
  }
}

export async function logout(): Promise<void> {
  const rt = getRefreshToken();
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  try {
    await fetch(`${API}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
  } catch {
    // ignore
  }
  clearAuth();
}
