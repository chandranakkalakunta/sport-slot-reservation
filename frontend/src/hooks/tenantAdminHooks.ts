import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";

export interface CatalogType { type_id: string; name: string; sport: string; }
export interface TenantFacility {
  id: string; facility_type_id: string; sport: string; name: string;
  open_time: string; close_time: string; slot_duration_minutes: number;
  description?: string | null; active: boolean;
}

export function useFacilityCatalog() {
  return useQuery({
    queryKey: ["facility-catalog"],
    queryFn: () => apiFetch<{ items: CatalogType[] }>("/facility-catalog"),
  });
}

export function useTenantFacilities() {
  return useQuery({
    queryKey: ["tenant", "facilities"],
    queryFn: () => apiFetch<{ items: TenantFacility[] }>("/tenant/facilities"),
  });
}

export function useCreateFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Omit<TenantFacility, "id" | "sport" | "active">) =>
      apiFetch<TenantFacility>("/tenant/facilities", {
        method: "POST", body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "facilities"] }),
  });
}

export function useUpdateFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Record<string, unknown>) =>
      apiFetch<TenantFacility>(`/tenant/facilities/${id}`, {
        method: "PATCH", body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "facilities"] }),
  });
}

export function useDeactivateFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/tenant/facilities/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "facilities"] }),
  });
}

export function useUpdateBranding() {
  return useMutation({
    mutationFn: (body: Record<string, string>) =>
      apiFetch("/tenant/branding", { method: "PATCH", body: JSON.stringify(body) }),
  });
}

export function useUpdatePolicies() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch("/tenant/policies", { method: "PATCH", body: JSON.stringify(body) }),
  });
}
