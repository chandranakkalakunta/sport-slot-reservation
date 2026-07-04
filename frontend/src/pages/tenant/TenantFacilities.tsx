import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { Button } from "../../components/ui/button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { ListRow } from "../../components/ListRow";
import { Input } from "../../components/ui/input";
import {
  emptyWeeklySchedule,
  WeeklyScheduleEditor,
} from "../../components/tenant/WeeklyScheduleEditor";
import {
  type TenantFacility,
  useCreateFacility,
  useDeactivateFacility,
  useFacilityCatalog,
  useTenantFacilities,
  useUpdateFacility,
} from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";
import type { WeeklySchedule } from "../../types/facilitySchedule";

export default function TenantFacilities() {
  const { data: catalog } = useFacilityCatalog();
  const { data: facilities, isLoading } = useTenantFacilities();
  const createFacility = useCreateFacility();
  const updateFacility = useUpdateFacility();
  const deactivate = useDeactivateFacility();

  // Create form state
  const [typeId, setTypeId] = useState("");
  const [name, setName] = useState("");
  const [duration, setDuration] = useState(60);
  const [description, setDescription] = useState("");
  const [schedule, setSchedule] = useState<WeeklySchedule>(emptyWeeklySchedule);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  // Edit dialog state
  const [editingFacility, setEditingFacility] = useState<TenantFacility | null>(null);
  const [editTypeId, setEditTypeId] = useState("");
  const [editName, setEditName] = useState("");
  const [editDuration, setEditDuration] = useState(60);
  const [editDescription, setEditDescription] = useState("");
  const [editSchedule, setEditSchedule] = useState<WeeklySchedule>(emptyWeeklySchedule);
  const [editError, setEditError] = useState<string | null>(null);
  const [editOk, setEditOk] = useState<string | null>(null);

  // Remove-confirm dialog state
  const [confirmFacilityId, setConfirmFacilityId] = useState<string | null>(null);

  function openEdit(f: TenantFacility) {
    setEditingFacility(f);
    setEditTypeId(f.facility_type_id);
    setEditName(f.name);
    setEditDuration(f.slot_duration_minutes);
    setEditDescription(f.description ?? "");
    setEditSchedule(f.weekly_schedule);
    setEditError(null);
    setEditOk(null);
  }

  function closeEdit() {
    setEditingFacility(null);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null); setOk(null);
    if (!typeId) { setError("Select a facility type."); return; }
    try {
      await createFacility.mutateAsync({
        facility_type_id: typeId,
        name,
        slot_duration_minutes: Number(duration),
        description: description || null,
        weekly_schedule: schedule,
      });
      setOk(`Created ${name}.`);
      setName(""); setDescription(""); setSchedule(emptyWeeklySchedule());
    } catch (e) {
      setError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to create facility.");
    }
  }

  async function submitEdit(e: FormEvent) {
    e.preventDefault();
    if (!editingFacility) return;
    setEditError(null); setEditOk(null);
    try {
      await updateFacility.mutateAsync({
        id: editingFacility.id,
        facility_type_id: editTypeId,
        name: editName,
        slot_duration_minutes: Number(editDuration),
        description: editDescription || null,
        weekly_schedule: editSchedule,
      });
      setEditOk(`Updated ${editName}.`);
    } catch (e) {
      setEditError(e instanceof ApiClientError ? messageForCode(e.code) : "Failed to update facility.");
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

        {/* Facility list */}
        <div className="space-y-2">
          {activeFacilities.map((f) => (
            <ListRow
              key={f.id}
              action={
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => openEdit(f)}
                  >
                    Edit
                  </Button>
                  {/* De-emphasized trigger per ADR-0028 §5; ConfirmDialog confirms before mutate */}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                    onClick={() => setConfirmFacilityId(f.id)}
                  >
                    Remove
                  </Button>
                </div>
              }
            >
              <p className="font-semibold text-foreground truncate">{f.name}</p>
              <p className="text-sm text-muted-foreground tabular-nums mt-0.5">
                {f.sport} · {f.slot_duration_minutes}min slots
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
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">Weekly schedule</p>
              <WeeklyScheduleEditor value={schedule} onChange={setSchedule} />
            </div>
            <Button type="submit" disabled={createFacility.isPending} className="w-full">
              {createFacility.isPending ? "Creating…" : "Add facility"}
            </Button>
          </form>
          {error && <p className="text-sm text-destructive">{error}</p>}
          {ok && <p className="text-sm text-success">{ok}</p>}
        </section>
      </main>

      {/* Edit facility dialog */}
      <Dialog open={editingFacility !== null} onOpenChange={(open) => { if (!open) closeEdit(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit facility</DialogTitle>
          </DialogHeader>
          <form onSubmit={submitEdit} className="space-y-3">
            <div className="space-y-1">
              <label htmlFor="edit-facility-type" className="text-sm font-medium text-foreground">
                Type
              </label>
              <select
                id="edit-facility-type"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                value={editTypeId}
                onChange={(e) => setEditTypeId(e.target.value)}
              >
                <option value="">Select a type…</option>
                {catalog?.items.map((c) => (
                  <option key={c.type_id} value={c.type_id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label htmlFor="edit-facility-name" className="text-sm font-medium text-foreground">
                Name
              </label>
              <Input
                id="edit-facility-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="edit-facility-duration" className="text-sm font-medium text-foreground">
                Slot duration (minutes)
              </label>
              <Input
                id="edit-facility-duration"
                type="number"
                value={editDuration}
                onChange={(e) => setEditDuration(Number(e.target.value))}
                required
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="edit-facility-desc" className="text-sm font-medium text-foreground">
                Description (optional)
              </label>
              <Input
                id="edit-facility-desc"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">Weekly schedule</p>
              <WeeklyScheduleEditor value={editSchedule} onChange={setEditSchedule} />
            </div>
            {editError && <p className="text-sm text-destructive">{editError}</p>}
            {editOk && <p className="text-sm text-success">{editOk}</p>}
            <Button type="submit" disabled={updateFacility.isPending} className="w-full">
              {updateFacility.isPending ? "Saving…" : "Save changes"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>

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
