"use client";

export interface AuthUser {
  id: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  role: string | null;
  email_verified: boolean;
  permissions?: string[];
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
  permissions?: string[];
  active_sessions: number;
}

export interface SessionItem {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  device_info: string | null;
  created_at: string | null;
  expires_at: string | null;
  is_active: boolean;
  revoked_at: string | null;
}

const TOKEN_KEY = "admin_at";
const REFRESH_KEY = "admin_rt";
const USER_KEY = "admin_user";
const PERMS_KEY = "admin_perms";

export function savePermissions(perms: string[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(PERMS_KEY, JSON.stringify(perms));
}

export function getPermissions(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(PERMS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function hasPermission(perm: string): boolean {
  const perms = getPermissions();
  if (perms.includes("*")) return true;
  return perms.includes(perm);
}

export function saveAuth(data: LoginResponse): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(REFRESH_KEY, data.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  if (data.user.permissions) {
    savePermissions(data.user.permissions);
  }
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(PERMS_KEY);
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

export async function twoFactorSetup(currentPassword: string): Promise<{ secret: string; otpauth_uri: string; message: string }> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = getAccessToken();
  const res = await fetch(`${API}/auth/2fa/setup`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ current_password: currentPassword }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "2FA setup failed");
  }
  return res.json();
}

export async function twoFactorEnable(code: string): Promise<{ message: string }> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = getAccessToken();
  const res = await fetch(`${API}/auth/2fa/enable`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "2FA enable failed");
  }
  return res.json();
}

export async function twoFactorDisable(code: string): Promise<{ message: string }> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = getAccessToken();
  const res = await fetch(`${API}/auth/2fa/disable`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "2FA disable failed");
  }
  return res.json();
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = getAccessToken();
  const res = await fetch(`${API}/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Password change failed");
  }
  return res.json();
}

export async function listSessions(): Promise<{ sessions: SessionItem[] }> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = getAccessToken();
  const res = await fetch(`${API}/auth/sessions`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (res.status === 401 && (await refreshAccessToken())) {
    return listSessions();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Failed to load sessions");
  }
  return res.json();
}

export async function revokeSession(sessionId: string): Promise<{ message: string }> {
  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const token = getAccessToken();
  const res = await fetch(`${API}/auth/sessions/${sessionId}`, {
    method: "DELETE",
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (res.status === 401 && (await refreshAccessToken())) {
    return revokeSession(sessionId);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || "Failed to revoke session");
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
