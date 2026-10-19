/**
 * RiskLens AI - Centralized Typed API Client
 * Connects to the FastAPI backend using VITE_API_BASE_URL.
 */

export class ApiError extends Error {
  public status: number;
  public statusText: string;
  public detail: string;
  public url: string;

  constructor(status: number, statusText: string, detail: string, url: string) {
    super(`API Error ${status} (${statusText}): ${detail}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
    this.url = url;
  }
}

export const DEFAULT_RENDER_URL = 'https://risklens-backend-3ddp.onrender.com';
export const DEFAULT_TUNNEL_URL = 'https://sees-legislature-scoop-friend.trycloudflare.com';

export const getBaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    const override = localStorage.getItem('risklens_api_url');
    if (override && override.trim()) {
      return override.trim().replace(/\/+$/, '');
    }
  }
  const url = import.meta.env.VITE_API_BASE_URL;
  if (url && typeof url === 'string' && url.trim()) {
    return url.trim().replace(/\/+$/, '');
  }
  // Production default for Vercel deployment: connect to live Render backend
  if (import.meta.env.PROD) {
    return DEFAULT_RENDER_URL;
  }
  return 'http://localhost:8000';
};

export const setBaseUrlOverride = (url: string | null): void => {
  if (typeof window !== 'undefined') {
    if (url && url.trim()) {
      localStorage.setItem('risklens_api_url', url.trim().replace(/\/+$/, ''));
    } else {
      localStorage.removeItem('risklens_api_url');
    }
  }
};

export const API_BASE_URL = getBaseUrl();

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  params?: Record<string, string | number | boolean | undefined | null>;
}

export async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 45000, params, headers, ...customConfig } = options;
  const baseUrl = getBaseUrl();

  let url = `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const defaultHeaders: HeadersInit = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
  };

  try {
    const response = await fetch(url, {
      ...customConfig,
      headers: {
        ...defaultHeaders,
        ...headers,
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorDetail = response.statusText;
      try {
        const errorJson = await response.json();
        if (errorJson && typeof errorJson === 'object') {
          if (typeof errorJson.detail === 'string') {
            errorDetail = errorJson.detail;
          } else if (Array.isArray(errorJson.detail)) {
            errorDetail = errorJson.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ');
          } else if (errorJson.message) {
            errorDetail = String(errorJson.message);
          }
        }
      } catch {
        // Response was not JSON, fallback to statusText
      }

      throw new ApiError(response.status, response.statusText, errorDetail, url);
    }

    // For 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError(408, 'Request Timeout', `Request timed out after ${timeoutMs}ms`, url);
    }

    const networkMsg = error instanceof Error ? error.message : 'Unknown network failure';
    throw new ApiError(0, 'Network Error', `Could not connect to RiskLens AI backend at ${baseUrl}. (${networkMsg})`, url);
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: 'DELETE' }),
};
