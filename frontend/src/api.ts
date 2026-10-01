const ACCESS = "ems.access";
const REFRESH = "ems.refresh";

const base = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS);
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH);
}

export function saveTokens(access: string, refresh: string): void {
  sessionStorage.setItem(ACCESS, access);
  sessionStorage.setItem(REFRESH, refresh);
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS);
  sessionStorage.removeItem(REFRESH);
}

async function readError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
    };
    return new ApiError(
      response.status,
      body.error?.code ?? "request_failed",
      body.error?.message ?? "The request failed.",
    );
  } catch {
    return new ApiError(response.status, "request_failed", "The request failed.");
  }
}

let refreshTask: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  if (!refreshTask) {
    refreshTask = fetch(`${base}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    })
      .then(async (response) => {
        if (!response.ok) {
          clearTokens();
          return false;
        }
        const body = (await response.json()) as {
          access_token: string;
          refresh_token: string;
        };
        saveTokens(body.access_token, body.refresh_token);
        return true;
      })
      .finally(() => {
        refreshTask = null;
      });
  }
  return refreshTask;
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const access = getAccessToken();
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const response = await fetch(`${base}/api/v1${path}`, { ...init, headers });
  if (response.status === 401 && retry && getRefreshToken() && !path.startsWith("/auth/login") && path !== "/auth/refresh") {
    const refreshed = await refreshAccess();
    if (refreshed) return api<T>(path, init, false);
  }
  if (!response.ok) throw await readError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
