import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import { useAuth } from "./AuthContext";

/** Returns whether the current user must change their password.
 *  Platform admins are excluded (seeded clean; profile lives
 *  outside the tenant path). The flag lives on the profile doc,
 *  fetched via /users/me. */
export function usePasswordGate(): { mustChange: boolean; loading: boolean } {
  const { claims } = useAuth();
  const isPlatformAdmin = claims?.role === "platform_admin";
  const { data, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: () => apiFetch<{ must_change_password?: boolean }>("/users/me"),
    enabled: !isPlatformAdmin,
  });
  if (isPlatformAdmin) return { mustChange: false, loading: false };
  return { mustChange: Boolean(data?.must_change_password), loading: isLoading };
}
