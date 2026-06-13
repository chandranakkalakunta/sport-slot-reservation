import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../lib/api";

export interface Facility {
  id: string;
  name: string;
  sport: string;
  slot_duration_minutes: number;
  open_time: string;
  close_time: string;
  active: boolean;
}

export interface Slot {
  start: string;
  end: string;
  status: "available" | "booked" | "past";
  bookable: boolean;
  reason: string | null;
}

export interface Availability {
  facility_id: string;
  date: string;
  slots: Slot[];
}

export interface Booking {
  id: string;
  facility_id: string;
  date: string;
  start: string;
  end: string;
  status: string;
  notice?: string;
  cancelled_at?: string | null;
}

export function useFacilities() {
  return useQuery({
    queryKey: ["facilities"],
    queryFn: () =>
      apiFetch<{ items: Facility[]; next_cursor: string | null }>("/facilities"),
  });
}

export function useAvailability(facilityId: string | null, date: string) {
  return useQuery({
    queryKey: ["availability", facilityId, date],
    queryFn: () =>
      apiFetch<Availability>(`/facilities/${facilityId}/availability?date=${date}`),
    enabled: !!facilityId,
  });
}

export function useCreateBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { facility_id: string; date: string; start: string }) =>
      apiFetch<Booking>("/bookings", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, vars) => {
      // Refresh the grid so the booked slot flips to unavailable.
      qc.invalidateQueries({
        queryKey: ["availability", vars.facility_id, vars.date],
      });
    },
  });
}

export function useMyBookings() {
  return useQuery({
    queryKey: ["my-bookings"],
    queryFn: () =>
      apiFetch<{ items: Booking[]; next_cursor: string | null }>("/bookings/mine"),
  });
}

export function useCancelBooking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (booking: { id: string; facility_id: string; date: string }) =>
      apiFetch<Booking>(`/bookings/${booking.id}/cancel`, { method: "POST" }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["my-bookings"] });
      qc.invalidateQueries({
        queryKey: ["availability", vars.facility_id, vars.date],
      });
    },
  });
}
