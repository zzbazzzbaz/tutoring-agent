import { STORAGE_KEYS, COOKIE_KEYS, API_URL } from "@/lib/constants";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.TOKEN);
}

function clearAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.TOKEN);
  localStorage.removeItem(STORAGE_KEYS.USER);
  document.cookie = `${COOKIE_KEYS.AUTH}=; path=/; max-age=0`;
  document.cookie = `${COOKIE_KEYS.ROLE}=; path=/; max-age=0`;
  // [调试模式] 路由拦截已临时禁用，见 docs/route-guard-debug.md
  // 恢复方法：取消下行注释
  // window.location.href = "/login";
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearAuth();
    throw new ApiError("UNAUTHORIZED", "登录已过期，请重新登录", 401);
  }

  if (!res.ok) {
    let code = "UNKNOWN_ERROR";
    let message = `请求失败 (${res.status})`;
    try {
      const body = await res.json();
      const error = body?.detail?.error;
      if (error) {
        code = error.code ?? code;
        message = error.message ?? message;
      }
    } catch {
      // response body is not JSON
    }
    throw new ApiError(code, message, res.status);
  }

  if (res.headers.get("content-type")?.includes("application/json")) {
    return res.json();
  }
  return res.blob() as unknown as T;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  delete: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "DELETE",
      body: body ? JSON.stringify(body) : undefined,
    }),
  postForm: <T>(path: string, formData: FormData) =>
    apiFetch<T>(path, {
      method: "POST",
      body: formData,
      headers: {},
    }),
  getBlob: (path: string) => apiFetch<Blob>(path, { method: "GET" }),
};
