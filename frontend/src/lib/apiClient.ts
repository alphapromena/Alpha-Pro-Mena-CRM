/**
 * API client with fetch wrapper, automatic credentials (cookies), silent token refresh,
 * and unified error handling.
 *
 * Auth model: the backend sets an HttpOnly `access_token` cookie (15 min) and a
 * `refresh_token` cookie (7 days). When a request comes back 401 we call
 * POST /auth/refresh once (de-duplicated across concurrent requests) and retry.
 * If the refresh fails the session is over and `auth:expired` is dispatched.
 */

const API_BASE = '/api/v1';

// Endpoints that must never trigger a refresh attempt.
//
// /auth/me is here because it is the app's own "who am I" probe: a 401 from it
// means there is no session, which is an answer, not a recoverable failure. Chasing
// it with /auth/refresh produced the paired 401s seen on every anonymous page load.
// The public auth endpoints are here for the same reason: a 401 from them is the
// result, and refreshing a session that does not exist cannot change it.
const NO_REFRESH = [
  '/auth/login',
  '/auth/refresh',
  '/auth/logout',
  '/auth/me',
  '/auth/verify-email',
  '/auth/resend-verification',
  '/auth/forgot-password',
  '/auth/reset-password',
];

/**
 * Whether the browser holds a session hint.
 *
 * The session cookies are HttpOnly, so the app cannot read them. The backend also
 * sets a non-secret `session_active` cookie alongside them, which is readable here
 * and lets an anonymous load skip the auth probe entirely instead of learning the
 * answer from a 401.
 */
export function hasSessionHint(): boolean {
  if (typeof document === 'undefined') return false;
  return document.cookie
    .split(';')
    .some((c) => c.trim().startsWith('session_active='));
}

export class ApiError extends Error {
  code: string;
  details: any[];
  status: number;

  constructor(message: string, code: string = 'ERROR', status: number = 500, details: any[] = []) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

let refreshInFlight: Promise<boolean> | null = null;

/** Try to mint a new access token from the refresh cookie. Shared across callers. */
function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {},
  isRetry = false
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const config: RequestInit = {
    ...options,
    headers,
    credentials: 'include', // Sends HttpOnly cookies
  };

  const response = await fetch(url, config);

  if (response.status === 401 && !isRetry && !NO_REFRESH.some((p) => endpoint.includes(p))) {
    if (await refreshSession()) {
      return apiRequest<T>(endpoint, options, true);
    }
    window.dispatchEvent(new CustomEvent('auth:expired'));
  }

  if (response.status === 204) {
    return {} as T;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errData = data.error || {};
    const message = errData.message || response.statusText || 'An error occurred';
    const code = errData.code || `HTTP_${response.status}`;
    throw new ApiError(message, code, response.status, errData.details || []);
  }

  return data;
}

export const api = {
  get: <T>(url: string, params?: Record<string, any>) => {
    let finalUrl = url;
    if (params) {
      const search = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          search.append(k, String(v));
        }
      });
      const qs = search.toString();
      if (qs) finalUrl += `?${qs}`;
    }
    return apiRequest<T>(finalUrl, { method: 'GET' });
  },
  post: <T>(url: string, body?: any) =>
    apiRequest<T>(url, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body || {}),
    }),
  patch: <T>(url: string, body?: any) =>
    apiRequest<T>(url, {
      method: 'PATCH',
      body: JSON.stringify(body || {}),
    }),
  delete: <T>(url: string) =>
    apiRequest<T>(url, {
      method: 'DELETE',
    }),
};
