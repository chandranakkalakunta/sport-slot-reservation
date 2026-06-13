const BASE_DOMAIN = "sportbook.chandraailabs.com";
const DEV_HOSTS = new Set(["localhost", "127.0.0.1"]);

/** Tenant slug from the hostname.
 *  - Real subdomain {slug}.sportbook.chandraailabs.com → that slug
 *    (production; the authoritative host-based path).
 *  - localhost / 127.0.0.1 → VITE_DEV_TENANT_SLUG (local dev).
 *  - Any other host (e.g. *.web.app, the single-tenant DEV
 *    surface) → VITE_DEFAULT_TENANT_SLUG if set, else null.
 *  On a real custom domain (Phase 7) the subdomain branch wins and
 *  the default is irrelevant. */
export function tenantSlugFromHost(host = window.location.hostname): string | null {
  const suffix = "." + BASE_DOMAIN;
  if (host.endsWith(suffix)) {
    return host.slice(0, -suffix.length);
  }
  if (DEV_HOSTS.has(host)) {
    return import.meta.env.VITE_DEV_TENANT_SLUG ?? null;
  }
  return import.meta.env.VITE_DEFAULT_TENANT_SLUG || null;
}
