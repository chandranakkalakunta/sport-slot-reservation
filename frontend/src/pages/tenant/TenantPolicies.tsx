import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { useUpdatePolicies } from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

export default function TenantPolicies() {
  const updatePolicies = useUpdatePolicies();

  const [horizonDays, setHorizonDays] = useState(14);
  const [openTime, setOpenTime] = useState("06:00");
  const [bufferHours, setBufferHours] = useState(1);
  const [maxSlots, setMaxSlots] = useState(2);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setOk(false);
    try {
      await updatePolicies.mutateAsync({
        booking_horizon_days: horizonDays,
        booking_window_open_time: openTime,
        cancellation_buffer_hours: bufferHours,
        max_slots_per_user_per_sport_per_day: maxSlots,
      });
      setOk(true);
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to save policies.");
    }
  }

  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-lg px-4 py-6 space-y-6">
        <Link to="/tenant" className="block text-sm font-medium text-link underline underline-offset-2 hover:text-link/70">← Dashboard</Link>
        <h1 className="text-2xl font-semibold text-foreground">Booking Policies</h1>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1">
            <label htmlFor="policy-horizon" className="text-sm font-medium text-foreground">
              Booking horizon (days)
            </label>
            <Input
              id="policy-horizon"
              type="number"
              min={1}
              value={horizonDays}
              onChange={(e) => setHorizonDays(Number(e.target.value))}
              required
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="policy-open" className="text-sm font-medium text-foreground">
              Booking window opens at (HH:MM)
            </label>
            <Input
              id="policy-open"
              className="tabular-nums"
              value={openTime}
              onChange={(e) => setOpenTime(e.target.value)}
              placeholder="06:00"
              required
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="policy-buffer" className="text-sm font-medium text-foreground">
              Cancellation buffer (hours before slot)
            </label>
            <Input
              id="policy-buffer"
              type="number"
              min={0}
              value={bufferHours}
              onChange={(e) => setBufferHours(Number(e.target.value))}
              required
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="policy-max" className="text-sm font-medium text-foreground">
              Max slots per user per sport per day
            </label>
            <Input
              id="policy-max"
              type="number"
              min={1}
              value={maxSlots}
              onChange={(e) => setMaxSlots(Number(e.target.value))}
              required
            />
          </div>
          <Button type="submit" disabled={updatePolicies.isPending} className="w-full">
            {updatePolicies.isPending ? "Saving…" : "Save policies"}
          </Button>
        </form>
        {ok && <p className="text-sm text-success">Saved ✓</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </main>
    </>
  );
}
