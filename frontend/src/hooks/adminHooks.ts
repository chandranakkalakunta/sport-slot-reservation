import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";

export interface Tenant {
  tenant_id: string;
  slug: string;
  display_name?: string;
  name?: string;
  active?: boolean;
  created_at?: string;
}

export interface CreatedUser {
  uid: string;
  temp_password: string;
}

export function useTenants() {
  return useQuery({
    queryKey: ["admin", "tenants"],
    queryFn: () => apiFetch<{ items: Tenant[] }>("/admin/tenants"),
  });
}

export function useCreateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { slug: string; display_name: string }) =>
      apiFetch<{ tenant_id: string; slug: string }>("/admin/tenants", {
        method: "POST", body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "tenants"] }),
  });
}

export function useCreateUser(tenantId: string) {
  return useMutation({
    mutationFn: (body: {
      email: string; display_name: string; flat_number?: string;
      role: string; household_id?: string | null;
    }) =>
      apiFetch<CreatedUser>(`/admin/tenants/${tenantId}/users`, {
        method: "POST", body: JSON.stringify(body),
      }),
  });
}
