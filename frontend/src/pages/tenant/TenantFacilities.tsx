import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { Button } from "../../components/ui/button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ListRow } from "../../components/ListRow";
import { Input } from "../../components/ui/input";
import {
  useCreateFacility, useDeactivateFacility, useFacilityCatalog,
  useTenantFacilities,
} from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

export default function TenantFacilities() {
  const { data: catalog } = useFacilityCatalog();
  const { data: facilities, isLoading } = useTenantFacilities();
  const createFacility = useCreateFacility();
  const deactivate = useDeactivateFacility();

  const [typeId, setTypeId] = useState("");
  const [name, setName] = useState("");
  const [openTime, setOpenTime] = useState("06:00");
  const [closeTime, setCloseTime] = useState("22:00");
  const [duration, setDuration] = useState(60);
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [confirmFacilityId, setConfirmFacilityId] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setOk(null);
    if (!typeId) { setError("Select a facility type."); return; }
    try {
      await createFacility.mutateAsync({
        facility_type_id: typeId, name, open_time: openTime,
        close_time: closeTime, slot_duration_minutes: Number(duration),
        description: description || null,
      });
      setOk(`Created ${name}.`);
      setName(""); setDescription("");
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to create facility.");
    }
  }

  const activeFacilities = (facilities?.items.filter((f) => f.active) ?? [])
    .sort((a, b) => a.name.localeCompare(b.name));

  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-6 space-y-6">
        <Link to="/tenant" className="block text-sm font-medium text-link underline underline-offset-2 hover:text-link/70">← Dashboard</Link>
        <h1 className="text-2xl font-semibold text-foreground">Facilities</h1>

        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

        {/* Facility list — standard ListRow (no flex-col stacking) */}
        <div className="space-y-2">
          {activeFacilities.map((f) => (
            <ListRow
              key={f.id}
              action={
                /* De-emphasized trigger per ADR-0028 §5; ConfirmDialog confirms before mutate */
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                  onClick={() => setConfirmFacilityId(f.id)}
                >
                  Remove
                </Button>
              }
            >
              <p className="font-semibold text-foreground truncate">{f.name}</p>
              <p className="text-sm text-muted-foreground tabular-nums mt-0.5">
                {f.sport} · {f.open_time}–{f.close_time} · {f.slot_duration_minutes}min
                {f.description ? ` · ${f.description}` : ""}
              </p>
            </ListRow>
          ))}
        </div>

        {/* Add facility form */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Add a facility</h2>
          <form onSubmit={submit} className="max-w-md space-y-3">
            <div className="space-y-1">
              <label htmlFor="facility-type" className="text-sm font-medium text-foreground">
                Type
              </label>
              <select
                id="facility-type"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                value={typeId}
                onChange={(e) => setTypeId(e.target.value)}
              >
                <option value="">Select a type…</option>
                {catalog?.items.map((c) => (
                  <option key={c.type_id} value={c.type_id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="facility-name" className="text-sm font-medium text-foreground">
                Name
              </label>
              <Input
                id="facility-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="North Side Court"
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="facility-open" className="text-sm font-medium text-foreground">
                Opens
              </label>
              <Input
                id="facility-open"
                className="tabular-nums"
                value={openTime}
                onChange={(e) => setOpenTime(e.target.value)}
                placeholder="06:00"
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="facility-close" className="text-sm font-medium text-foreground">
                Closes
              </label>
              <Input
                id="facility-close"
                className="tabular-nums"
                value={closeTime}
                onChange={(e) => setCloseTime(e.target.value)}
                placeholder="22:00"
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="facility-duration" className="text-sm font-medium text-foreground">
                Slot duration (minutes)
              </label>
              <Input
                id="facility-duration"
                type="number"
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="facility-desc" className="text-sm font-medium text-foreground">
                Description (optional)
              </label>
              <Input
                id="facility-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={createFacility.isPending} className="w-full">
              {createFacility.isPending ? "Creating…" : "Add facility"}
            </Button>
          </form>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {ok && <p className="text-sm text-success">{ok}</p>}
        </section>
      </main>

      {confirmFacilityId && (
        <ConfirmDialog
          title="Remove facility"
          body={<p>Remove this facility? Active bookings may be affected.</p>}
          confirmLabel="Remove"
          busy={deactivate.isPending}
          onConfirm={() => { deactivate.mutate(confirmFacilityId); setConfirmFacilityId(null); }}
          onCancel={() => setConfirmFacilityId(null)}
        />
      )}
    </>
  );
}
