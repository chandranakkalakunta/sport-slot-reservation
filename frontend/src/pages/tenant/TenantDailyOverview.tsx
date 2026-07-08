import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import {
  type OverviewBooking,
  type OverviewFacility,
  type OverviewSlot,
  useDailyOverview,
} from "../../hooks/tenantAdminHooks";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

// Unique facility types from the loaded facilities, for the filter dropdown.
function facilityTypes(facilities: OverviewFacility[]): string[] {
  const types = new Set(facilities.map((f) => f.facility_type_id));
  return Array.from(types).sort();
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

interface TooltipProps {
  id: string;
  name: string | null;
  email: string | null;
}

function ResidentTooltip({ id, name, email }: TooltipProps) {
  return (
    <div
      id={id}
      role="tooltip"
      className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-max max-w-[200px] rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md pointer-events-none"
    >
      <p className="font-medium">{name ?? "Unknown"}</p>
      <p className="text-muted-foreground">{email ?? ""}</p>
    </div>
  );
}

// ── Slot cell (used in Grid view) ─────────────────────────────────────────────

interface SlotCellProps {
  slot: OverviewSlot;
  cellId: string;
}

function SlotCell({ slot, cellId }: SlotCellProps) {
  const [visible, setVisible] = useState(false);
  const tooltipId = `tooltip-${cellId}`;

  const cancelled = slot.status === "cancelled";
  const cellClass = cancelled
    ? "relative inline-flex items-center justify-center rounded px-1.5 py-0.5 text-xs font-medium bg-muted text-muted-foreground line-through cursor-default"
    : "relative inline-flex items-center justify-center rounded px-1.5 py-0.5 text-xs font-medium bg-primary/15 text-primary cursor-default";

  return (
    <span
      className={cellClass}
      tabIndex={0}
      aria-describedby={tooltipId}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {slot.start}
      {visible && (
        <ResidentTooltip
          id={tooltipId}
          name={slot.resident_name}
          email={slot.resident_email}
        />
      )}
    </span>
  );
}

// Open/available slot — no resident info, so no tooltip or focus wiring.
function AvailableCell({ start }: { start: string }) {
  return (
    <span className="inline-flex items-center justify-center rounded px-1.5 py-0.5 text-xs font-medium bg-success/15 text-success">
      {start}
    </span>
  );
}

// ── List view ─────────────────────────────────────────────────────────────────

interface ListRowProps {
  booking: OverviewBooking;
}

function ListBookingRow({ booking }: ListRowProps) {
  const [visible, setVisible] = useState(false);
  const tooltipId = `tooltip-list-${booking.booking_id}`;
  const cancelled = booking.status === "cancelled";

  return (
    <div
      className={`relative flex items-center justify-between gap-3 rounded-md px-3 py-2 text-sm ${
        cancelled ? "bg-muted text-muted-foreground" : "bg-card text-foreground border border-border"
      }`}
      tabIndex={0}
      aria-describedby={tooltipId}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      <span className={cancelled ? "line-through tabular-nums" : "tabular-nums font-medium"}>
        {booking.start}–{booking.end}
      </span>
      <span className="text-xs text-muted-foreground shrink-0">
        {cancelled ? "Cancelled" : "Confirmed"}
      </span>
      {visible && (
        <ResidentTooltip
          id={tooltipId}
          name={booking.resident_name}
          email={booking.resident_email}
        />
      )}
    </div>
  );
}

// ── Grid view ─────────────────────────────────────────────────────────────────

interface GridViewProps {
  facilities: OverviewFacility[];
}

function GridView({ facilities }: GridViewProps) {
  // Collect all unique start times across all facilities' FULL slot geometry
  // (not just booked times) — this is what gives the Grid its capacity view.
  const allStarts = Array.from(
    new Set(facilities.flatMap((f) => f.slots.map((s) => s.start))),
  ).sort();

  if (allStarts.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No bookings on this date.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm border-separate border-spacing-0">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-background px-3 py-2 text-left font-medium text-foreground border-b border-border min-w-[140px]">
              Facility
            </th>
            {allStarts.map((t) => (
              <th
                key={t}
                className="px-2 py-2 text-center font-medium text-foreground border-b border-border tabular-nums whitespace-nowrap min-w-[72px]"
              >
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {facilities.map((fac) => {
            const byStart: Record<string, OverviewSlot> = {};
            for (const s of fac.slots) byStart[s.start] = s;
            return (
              <tr key={fac.facility_id} className="even:bg-muted/30">
                <td className="sticky left-0 z-10 bg-background px-3 py-2 font-medium text-foreground whitespace-nowrap border-b border-border/50">
                  {fac.name}
                </td>
                {allStarts.map((t) => {
                  const slot = byStart[t];
                  return (
                    <td
                      key={t}
                      className="px-2 py-2 text-center border-b border-border/50"
                    >
                      {!slot ? (
                        <span className="text-muted-foreground text-xs">—</span>
                      ) : slot.status === "available" ? (
                        <AvailableCell start={slot.start} />
                      ) : (
                        <SlotCell slot={slot} cellId={`${fac.facility_id}-${slot.start}`} />
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── List view (full) ──────────────────────────────────────────────────────────

interface ListViewProps {
  facilities: OverviewFacility[];
}

function ListView({ facilities }: ListViewProps) {
  const anyBookings = facilities.some((f) => f.bookings.length > 0);
  if (!anyBookings) {
    return (
      <p className="text-sm text-muted-foreground">No bookings on this date.</p>
    );
  }

  return (
    <div className="space-y-6">
      {facilities.map((fac) => (
        <section key={fac.facility_id}>
          <h2 className="text-base font-semibold text-foreground mb-2">
            {fac.name}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {fac.sport}
            </span>
          </h2>
          {fac.bookings.length === 0 ? (
            <p className="text-sm text-muted-foreground pl-1">No bookings.</p>
          ) : (
            <div className="space-y-1.5">
              {fac.bookings.map((b) => (
                <ListBookingRow key={b.booking_id} booking={b} />
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type ViewMode = "grid" | "list";

function useIsWideViewport(): boolean {
  const [isWide, setIsWide] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(min-width: 640px)").matches
      : true,
  );
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(min-width: 640px)");
    const handler = (e: MediaQueryListEvent) => setIsWide(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return isWide;
}

export default function TenantDailyOverview() {
  const [date, setDate] = useState(todayISO());
  const [typeFilter, setTypeFilter] = useState("all");
  const isWide = useIsWideViewport();
  const [manualMode, setManualMode] = useState<ViewMode | null>(null);

  const effectiveMode: ViewMode = manualMode ?? (isWide ? "grid" : "list");

  const { data, isLoading } = useDailyOverview(date);

  // Client-side alphabetical sort mirrors the backend's guarantee, so the
  // page remains correct even if the API is called with an older backend version.
  const allFacilities = [...(data?.facilities ?? [])].sort(
    (a, b) => (a.name ?? "").toLowerCase().localeCompare((b.name ?? "").toLowerCase()),
  );
  const types = facilityTypes(allFacilities);
  const filtered =
    typeFilter === "all"
      ? allFacilities
      : allFacilities.filter((f) => f.facility_type_id === typeFilter);

  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-7xl px-4 py-6 space-y-5">
        <Link
          to="/tenant"
          className="block text-sm font-medium text-link underline underline-offset-2 hover:text-link/70"
        >
          ← Admin Dashboard
        </Link>
        <h1 className="text-2xl font-semibold text-foreground">
          Daily Booking Overview
        </h1>

        {/* Controls */}
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4">
          {/* Date picker */}
          <div className="flex items-center gap-2">
            <label
              htmlFor="overview-date"
              className="text-sm font-medium text-foreground"
            >
              Date
            </label>
            <input
              id="overview-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full min-w-[160px] sm:w-auto rounded-md border border-input bg-background px-3 py-1.5 text-sm tabular-nums text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {/* Facility type filter */}
          {types.length > 0 && (
            <div className="flex items-center gap-2">
              <label
                htmlFor="type-filter"
                className="text-sm font-medium text-foreground"
              >
                Type
              </label>
              <select
                id="type-filter"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="all">All types</option>
                {types.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* View toggle */}
          <div
            className="sm:ml-auto flex rounded-md border border-border overflow-hidden"
            role="group"
            aria-label="View mode"
          >
            <button
              type="button"
              onClick={() => setManualMode("grid")}
              aria-pressed={effectiveMode === "grid"}
              className={`px-3 py-1.5 text-sm font-medium ${
                effectiveMode === "grid"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-foreground hover:bg-accent"
              }`}
            >
              Grid
            </button>
            <button
              type="button"
              onClick={() => setManualMode("list")}
              aria-pressed={effectiveMode === "list"}
              className={`px-3 py-1.5 text-sm font-medium border-l border-border ${
                effectiveMode === "list"
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-foreground hover:bg-accent"
              }`}
            >
              List
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded bg-success/15 border border-success/30" />
            Available
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded bg-primary/15 border border-primary/30" />
            Confirmed
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded bg-muted border border-border" />
            Cancelled
          </span>
        </div>

        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}

        {data && (
          effectiveMode === "grid" ? (
            <GridView facilities={filtered} />
          ) : (
            <ListView facilities={filtered} />
          )
        )}
      </main>
    </>
  );
}
