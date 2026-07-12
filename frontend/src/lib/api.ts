import { auth } from "./firebase";

// Module-level handler: called by AuthContext to receive notifications when a
// claims-related 401 is detected, so AuthContext can show the retry UI without
// a circular dependency (api.ts → AuthContext is avoided; AuthContext → api.ts).
let _claimsErrorHandler: (() => void) | null = null;

/** Registers (or clears) the callback that fires on an AUTH_INVALID_TOKEN 401
 *  with "Token missing provisioned claims". Called once by AuthContext on mount. */
export function setClaimsErrorHandler(fn: (() => void) | null): void {
  _claimsErrorHandler = fn;
}

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
  // FormData bodies (multipart, e.g. voice audio upload) must NOT get a
  // manual Content-Type — the browser sets it, including the boundary.
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`/api/v1${path}`, { ...init, headers });
  const body = await resp.json().catch(() => ({}));

  if (!resp.ok) {
    // Detect the stale-claims-after-fresh-sign-in case specifically.
    // "Token verification failed" (genuinely bad/expired token) and
    // AUTH_MISSING_TOKEN are different failure modes — not signalled here.
    if (
      resp.status === 401 &&
      body.code === "AUTH_INVALID_TOKEN" &&
      body.message === "Token missing provisioned claims"
    ) {
      _claimsErrorHandler?.();
    }
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
