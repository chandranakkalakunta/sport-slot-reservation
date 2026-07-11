import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";
import type { WeeklySchedule } from "../types/facilitySchedule";
import type { InvoiceLineItem } from "./invoiceHooks";

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
  invoice_generation_time?: string;
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

export interface LatestInvoice {
  invoice_id: string;
  household_id: string;
  flat_number: string | null;
  period: string;
  total_paise: number;
}

export function useTenantLatestInvoices() {
  return useQuery({
    queryKey: ["tenant", "invoices", "latest"],
    queryFn: () => apiFetch<{ items: LatestInvoice[] }>("/invoices/tenant/latest"),
  });
}

export interface InvoiceHistoryEntry {
  invoice_id: string;
  household_id: string;
  flat_number: string | null;
  period: string;
  total_paise: number;
  line_items: InvoiceLineItem[];
}

export function useTenantInvoiceHistory(householdId: string | null) {
  return useQuery({
    queryKey: ["tenant", "invoices", "history", householdId],
    queryFn: () =>
      apiFetch<{ items: InvoiceHistoryEntry[] }>(
        `/invoices/tenant/history?household_id=${encodeURIComponent(householdId ?? "")}`,
      ),
    enabled: !!householdId,
  });
}

export interface InvoicePreview {
  household_id: string;
  period: string;
  period_start: string;
  period_end: string;
  flat_number: string | null;
  line_items: InvoiceLineItem[];
  total_paise: number;
  preview: true;
}

export function useTenantInvoicePreview(householdId: string | null) {
  return useQuery({
    queryKey: ["tenant", "invoices", "preview", householdId],
    queryFn: () =>
      apiFetch<InvoicePreview>(
        `/invoices/tenant/preview?household_id=${encodeURIComponent(householdId ?? "")}`,
      ),
    enabled: !!householdId,
  });
}

export interface RegenerateSummary {
  tenant_id: string;
  period: string;
  households_invoiced: number;
  households_skipped: number;
  households_failed: { tenant_id: string; household_id: string; reason: string }[];
}

export function useRegenerateInvoices() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (period?: string) =>
      apiFetch<RegenerateSummary>(
        `/invoices/tenant/regenerate${period ? `?period=${encodeURIComponent(period)}` : ""}`,
        { method: "POST" },
      ),
    // Regeneration may create new invoices — refresh the latest-per-flat list
    // and any open household detail (history/preview share this key prefix).
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tenant", "invoices"] }),
  });
}

export interface ExportResult {
  csv_path: string;
  json_path: string;
  row_count: number;
}

export function useReExportInvoices() {
  return useMutation({
    mutationFn: (period?: string) =>
      apiFetch<ExportResult>(
        `/invoices/tenant/export${period ? `?period=${encodeURIComponent(period)}` : ""}`,
        { method: "POST" },
      ),
  });
}

export interface ExportDownloadUrls {
  csv_url: string;
  json_url: string;
}

export function useInvoiceExportDownloadUrls() {
  return useMutation({
    mutationFn: (period?: string) =>
      apiFetch<ExportDownloadUrls>(
        `/invoices/tenant/export/download${period ? `?period=${encodeURIComponent(period)}` : ""}`,
      ),
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
