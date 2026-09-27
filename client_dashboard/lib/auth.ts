"use client";

export interface AuthUser {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  role: string | null;
  email_verified: boolean;
  two_factor_enabled?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
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

const TOKEN_KEY = "client_at";
const REFRESH_KEY = "client_rt";
const USER_KEY = "client_user";

/**
 * Backend API base path. All requests go through Next.js rewrites
 * (/_api/* → backend) so the browser never hits 127.0.0.1 directly.
 * This works on localhost, Cloudflare tunnels, and production domains.
 */
const API = () => "/_api";

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

export async function login(email: string, password: string): Promise<LoginResponse | TwoFactorRequired> {
  const res = await fetch(`${API()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Login failed");
  }
  const data = (await res.json()) as LoginResponse | TwoFactorRequired;
  if (!data || !("two_factor_required" in data)) {
    saveAuth(data as LoginResponse);
  }
  return data;
}

export async function verify2FA(twoFactorToken: string, code: string): Promise<LoginResponse> {
  const res = await fetch(`${API()}/auth/2fa/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, two_factor_token: twoFactorToken }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Verification failed");
  }
  const data: LoginResponse = await res.json();
  saveAuth(data);
  return data;
}

export async function register(data: {
  email: string; password: string; first_name?: string; last_name?: string;
}): Promise<{ id: string; message: string; verification_sent: boolean }> {
  const res = await fetch(`${API()}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Registration failed");
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
  try {
    const res = await fetch(`${API()}/auth/refresh`, {
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
  try {
    await fetch(`${API()}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
  } catch {
    // ignore
  }
  clearAuth();
}

export async function logoutAll(): Promise<void> {
  const token = getAccessToken();
  try {
    await fetch(`${API()}/auth/logout-all`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    // ignore
  }
  clearAuth();
}

export async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let token = getAccessToken();

  const doFetch = (tok: string | null) => {
    const isForm = init?.body instanceof FormData;
    const h: Record<string, string> = {};
    if (!isForm) h["Content-Type"] = "application/json";
    if (tok) h["Authorization"] = `Bearer ${tok}`;
    return fetch(`${API()}${path}`, { ...init, headers: { ...h, ...init?.headers } });
  };

  let res = await doFetch(token);
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      token = newToken;
      res = await doFetch(token);
    }
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        msg = body.detail;
      } else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        msg = body.detail[0].msg;
      }
    } catch {
      /* keep fallback message */
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  const res = await fetch(`${API()}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  return res.json();
}

export async function resetPassword(email: string, code: string, new_password: string): Promise<{ message: string }> {
  const res = await fetch(`${API()}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code, new_password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Reset failed");
  }
  return res.json();
}

export async function changePassword(current_password: string, new_password: string): Promise<{ message: string }> {
  const res = await fetch(`${API()}/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAccessToken()}` },
    body: JSON.stringify({ current_password, new_password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Password change failed");
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// 2FA (self-scoped) + session management
// ---------------------------------------------------------------------------
export interface MeResponse {
  id: string;
  email: string | null;
  telegram_id: number | null;
  first_name: string | null;
  last_name: string | null;
  language: string;
  timezone: string | null;
  role: string | null;
  account_status: string;
  email_verified: boolean;
  two_factor_enabled: boolean;
  two_factor_pending: boolean;
  created_at: string | null;
  last_login: string | null;
  active_sessions: number;
  has_password: boolean;
}

export const getMe = () => authFetch<MeResponse>("/auth/me");

export async function setup2FA(current_password: string): Promise<{ secret: string; otpauth_uri: string; message: string }> {
  const res = await authFetch<{ secret: string; otpauth_uri: string; message: string }>("/auth/2fa/setup", {
    method: "POST",
    body: JSON.stringify({ current_password }),
  });
  return res;
}

export const enable2FA = (code: string) =>
  authFetch<{ message: string }>("/auth/2fa/enable", { method: "POST", body: JSON.stringify({ code }) });

export const disable2FA = (code: string) =>
  authFetch<{ message: string }>("/auth/2fa/disable", { method: "POST", body: JSON.stringify({ code }) });

export interface SessionInfo {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  device_info: string | null;
  created_at: string | null;
  expires_at: string | null;
  is_active: boolean;
  revoked_at: string | null;
}

export const listSessions = () => authFetch<{ sessions: SessionInfo[] }>("/auth/sessions");
export const revokeSession = (sessionId: string) =>
  authFetch<{ message: string }>(`/auth/sessions/${sessionId}`, { method: "DELETE" });
