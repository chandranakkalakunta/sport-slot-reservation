import { tenantSlugFromHost } from "./tenant";

export interface Branding {
  slug: string;
  brand_name: string;
  brand_primary_color: string;
  brand_secondary_color: string;
}

/** Fetch public branding (no auth) and apply to CSS variables.
 * Called before/independent of login so the sign-in page is
 * branded. Falls back silently to theme.css defaults on any error. */
export async function loadBranding(): Promise<Branding | null> {
  const slug = tenantSlugFromHost();
  if (!slug) return null;
  try {
    const resp = await fetch(`/api/v1/tenants/${slug}/branding`);
    if (!resp.ok) return null;
    const b = (await resp.json()) as Branding;
    const root = document.documentElement;
    root.style.setProperty("--color-primary", b.brand_primary_color);
    root.style.setProperty("--color-secondary", b.brand_secondary_color);
    return b;
  } catch {
    return null;
  }
}
