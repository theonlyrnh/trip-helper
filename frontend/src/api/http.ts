const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const encodedName = `${encodeURIComponent(name)}=`;
  const value = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(encodedName));
  return value ? decodeURIComponent(value.slice(encodedName.length)) : null;
}

// Undefined means no token has been observed yet, so a compatible CSRF cookie
// may be used. Null is an explicit session clear and must not revive a stale cookie.
let csrfToken: string | null | undefined;

export function setCsrfToken(token: string | null | undefined): void {
  csrfToken = token || null;
}

export function getCsrfToken(): string | null {
  return csrfToken === undefined ? readCookie("csrf_token") : csrfToken;
}

export function apiUrl(path: string): string {
  return `${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;
}

function notifySessionExpired(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("trip-helper:session-expired"));
  }
}

function updateCsrfToken(response: Response): void {
  const token = response.headers.get("x-csrf-token");
  if (token) setCsrfToken(token);
}

function isUnsafeMethod(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

function isFormData(body: BodyInit | null | undefined): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

export function messageFromApiBody(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const payload = body as Record<string, unknown>;
  if (typeof payload.message === "string") return payload.message;
  if (typeof payload.detail === "string") return payload.detail;
  if (!Array.isArray(payload.detail)) return null;

  const firstProblem = payload.detail.find((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
  return typeof firstProblem?.msg === "string" ? firstProblem.msg : null;
}

function errorFromResponse(response: Response, body: unknown): ApiError {
  const payload = body && typeof body === "object" ? body as Record<string, unknown> : {};
  const code = typeof payload.code === "string" ? payload.code : null;
  const bodyMessage = messageFromApiBody(body);
  const message = bodyMessage
    ? bodyMessage
    : response.status === 401
      ? "登录状态已失效，请重新登录。"
      : response.status === 403
        ? "当前账号没有执行此操作的权限。"
        : "请求未能完成，请稍后重试。";
  return new ApiError(response.status, message, code);
}

async function readJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method || "GET";
  const headers = new Headers(init.headers);
  const body = init.body;

  headers.set("Accept", "application/json");
  if (body != null && !isFormData(body) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getCsrfToken();
  if (isUnsafeMethod(method) && token && !headers.has("X-CSRF-Token")) {
    headers.set("X-CSRF-Token", token);
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    method,
    body,
    headers,
    credentials: "include",
  });
  updateCsrfToken(response);

  const parsed = await readJson(response);
  if (!response.ok) {
    if (response.status === 401) notifySessionExpired();
    throw errorFromResponse(response, parsed);
  }
  return parsed as T;
}

function filenameFromDisposition(value: string | null, fallback: string): string {
  if (!value) return fallback;
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i);
  const quoted = value.match(/filename="?([^";]+)"?/i);
  const candidate = utf8?.[1] || quoted?.[1];
  if (!candidate) return fallback;
  try {
    return decodeURIComponent(candidate).replace(/[\\/\0]/g, "_");
  } catch {
    return fallback;
  }
}

export async function authenticatedDownload(path: string, fallbackFilename: string): Promise<void> {
  const response = await fetch(apiUrl(path), { credentials: "include" });
  updateCsrfToken(response);
  if (!response.ok) {
    if (response.status === 401) notifySessionExpired();
    throw errorFromResponse(response, await readJson(response));
  }
  const objectUrl = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filenameFromDisposition(response.headers.get("content-disposition"), fallbackFilename);
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export async function authenticatedBlob(path: string): Promise<Blob> {
  const response = await fetch(apiUrl(path), { credentials: "include" });
  updateCsrfToken(response);
  if (!response.ok) {
    if (response.status === 401) notifySessionExpired();
    throw errorFromResponse(response, await readJson(response));
  }
  return response.blob();
}
