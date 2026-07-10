import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import type { WeeklySchedule } from "../types/facilitySchedule";

export interface CatalogType { type_id: string; name: string; sport: string; }
export interface TenantFacility {
  id: string; facility_type_id: string; sport: string; name: string;
  weekly_schedule: WeeklySchedule; slot_duration_minutes: number;
  description?: string | null; active: boolean;
  price_paise?: number | null;
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

export interface UpdateFacilityPayload {
  id: string;
  name?: string;
  facility_type_id?: string;
  description?: string | null;
  slot_duration_minutes?: number;
  weekly_schedule?: WeeklySchedule;
  price_paise?: number | null;
}

export function useUpdateFacility() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: UpdateFacilityPayload) =>
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

export interface Policies {
  booking_horizon_days?: number;
  booking_window_open_time?: string;
  cancellation_buffer_hours?: number;
  max_slots_per_user_per_sport_per_day?: number;
}

export function usePolicies() {
  return useQuery({
    queryKey: ["tenant", "policies"],
    queryFn: () => apiFetch<{ policies: Policies }>("/tenant/policies"),
  });
}

export function useUpdatePolicies() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch("/tenant/policies", { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "policies"] }),
  });
}

export interface TenantUser {
  uid: string; email: string; display_name: string; role: string;
  flat_number?: string | null; active?: boolean; must_change_password?: boolean;
}

export function useTenantUsers() {
  return useQuery({
    queryKey: ["tenant", "users"],
    queryFn: () => apiFetch<{ items: TenantUser[] }>("/tenant/users"),
  });
}

export function useCreateTenantUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; display_name: string;
      flat_number?: string | null; role: string }) =>
      apiFetch<{ uid: string; temp_password: string }>("/tenant/users", {
        method: "POST", body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "users"] }),
  });
}

export function useDeactivateTenantUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (uid: string) => apiFetch(`/tenant/users/${uid}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "users"] }),
  });
}

export function useDeleteTenantUserPermanently() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (uid: string) =>
      apiFetch(`/tenant/users/${uid}/permanent`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "users"] }),
  });
}

export function useResetTenantUserPassword() {
  return useMutation({
    mutationFn: (uid: string) =>
      apiFetch<{ uid: string; temp_password: string }>(
        `/tenant/users/${uid}/reset-password`, { method: "POST" }),
  });
}

// ── Daily Booking Overview ───────────────────────────────────────────────────

export interface OverviewBooking {
  booking_id: string;
  start: string;
  end: string;
  status: "confirmed" | "cancelled";
  resident_name: string | null;
  resident_email: string | null;
}

export interface OverviewSlot {
  start: string;
  end: string;
  status: "available" | "confirmed" | "cancelled";
  resident_name: string | null;
  resident_email: string | null;
}

export interface OverviewFacility {
  facility_id: string;
  name: string;
  facility_type_id: string;
  sport: string;
  bookings: OverviewBooking[];
  slots: OverviewSlot[];
}

export interface DailyOverview {
  date: string;
  facilities: OverviewFacility[];
}

export function useDailyOverview(date: string) {
  return useQuery({
    queryKey: ["tenant", "overview", "daily", date],
    queryFn: () => apiFetch<DailyOverview>(`/tenant/overview/daily?date=${date}`),
    enabled: Boolean(date),
  });
}

export function useBulkCreateUsers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (rows: Record<string, unknown>[]) =>
      apiFetch<{ total: number; created: number; failed: number;
        results: { row: number; email: string; status: string;
          temp_password?: string; reason?: string }[] }>(
        "/tenant/users/bulk", { method: "POST", body: JSON.stringify({ rows }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "users"] }),
  });
}
