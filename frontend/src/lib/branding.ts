import { tenantSlugFromHost } from "./tenant";

export interface Branding {
  slug: string;
  brand_name: string;
  brand_primary_color: string;
  brand_secondary_color: string;
  brand_logo_url?: string | null;
}

let _current: Branding | null = null;

/** Returns the last successfully loaded Branding object (set at login/startup). */
export function getLastBranding(): Branding | null {
  return _current;
}

function applyBranding(b: Branding): void {
  const root = document.documentElement;
  root.style.setProperty("--color-primary", b.brand_primary_color);
  root.style.setProperty("--color-secondary", b.brand_secondary_color);
  _current = b;
}

async function fetchBranding(slug: string): Promise<Branding | null> {
  try {
    const resp = await fetch(`/api/v1/tenants/${slug}/branding`);
    if (!resp.ok) return null;
    return (await resp.json()) as Branding;
  } catch {
    return null;
  }
}

/** Pre-login: resolve slug from host (default-tenant fallback on
 * non-subdomain hosts) and apply. Silent on failure. */
export async function loadBranding(): Promise<Branding | null> {
  const slug = tenantSlugFromHost();
  if (!slug) return null;
  const b = await fetchBranding(slug);
  if (b) applyBranding(b);
  return b;
}

/** Post-login: re-resolve from the authoritative JWT slug claim. */
export async function loadBrandingForSlug(slug: string): Promise<Branding | null> {
  const b = await fetchBranding(slug);
  if (b) applyBranding(b);
  return b;
}
