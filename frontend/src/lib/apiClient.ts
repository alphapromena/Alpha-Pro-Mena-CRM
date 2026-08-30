/**
 * API client with fetch wrapper, automatic credentials (cookies), and unified error handling.
 */

const API_BASE = '/api/v1';

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

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
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

  if (response.status === 204) {
    return {} as T;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errData = data.error || {};
    const message = errData.message || response.statusText || 'An error occurred';
    const code = errData.code || `HTTP_${response.status}`;

    if (response.status === 401 && !endpoint.includes('/auth/login')) {
      // Auto-trigger auth expiration redirect if needed
      window.dispatchEvent(new CustomEvent('auth:expired'));
    }

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
