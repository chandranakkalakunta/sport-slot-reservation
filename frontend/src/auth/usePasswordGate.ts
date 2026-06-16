import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { useAuth } from "./AuthContext";

/** Shared with anything that mutates must_change_password (e.g.
 *  ForcePasswordChange) so the gate's cache can be refreshed under
 *  the exact key it reads — never re-derive this string elsewhere. */
export const PASSWORD_GATE_QUERY_KEY = ["profile"] as const;

/** Returns whether the current user must change their password.
 *  Platform admins are excluded (seeded clean; profile lives
 *  outside the tenant path). The flag lives on the profile doc,
 *  fetched via /users/me. */
export function usePasswordGate(): { mustChange: boolean; loading: boolean } {
  const { claims } = useAuth();
  const isPlatformAdmin = claims?.role === "platform_admin";
  const { data, isLoading } = useQuery({
    queryKey: PASSWORD_GATE_QUERY_KEY,
    queryFn: () => apiFetch<{ must_change_password?: boolean }>("/users/me"),
    enabled: !isPlatformAdmin,
  });
  if (isPlatformAdmin) return { mustChange: false, loading: false };
  return { mustChange: Boolean(data?.must_change_password), loading: isLoading };
}
