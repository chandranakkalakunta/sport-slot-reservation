const BASE_DOMAIN = "sportbook.chandraailabs.com";
const DEV_HOSTS = new Set(["localhost", "127.0.0.1"]);

/** Tenant slug from the hostname (branding, pre-login). On localhost
 * uses VITE_DEV_TENANT_SLUG — mirrors the backend dev override. */
export function tenantSlugFromHost(host = window.location.hostname): string | null {
  if (DEV_HOSTS.has(host)) {
    return import.meta.env.VITE_DEV_TENANT_SLUG ?? null;
  }
  const suffix = "." + BASE_DOMAIN;
  if (host.endsWith(suffix)) {
    return host.slice(0, -suffix.length);
  }
  return null;
}
