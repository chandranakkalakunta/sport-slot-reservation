import { auth } from "./firebase";

export interface ApiError {
  code: string;
  message: string;
  request_id?: string;
  status: number;
  detail?: { loc: (string | number)[]; msg: string }[];
}

export class ApiClientError extends Error {
  code: string;
  request_id?: string;
  status: number;
  detail?: { loc: (string | number)[]; msg: string }[];
  constructor(e: ApiError) {
    super(e.message);
    this.code = e.code;
    this.request_id = e.request_id;
    this.status = e.status;
    this.detail = e.detail;
  }
}

/** Same-origin API call (Vite proxy in dev, Hosting rewrites in
 * prod). Injects the current Firebase ID token. */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await auth.currentUser?.getIdToken();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`/api/v1${path}`, { ...init, headers });
  const body = await resp.json().catch(() => ({}));

  if (!resp.ok) {
    throw new ApiClientError({
      code: body.code ?? "UNKNOWN",
      message: body.message ?? resp.statusText,
      request_id: body.request_id,
      status: resp.status,
      detail: body.detail,
    });
  }
  return body as T;
}
