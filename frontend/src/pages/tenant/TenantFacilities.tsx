import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import {
  useCreateFacility, useDeactivateFacility, useFacilityCatalog,
  useTenantFacilities,
} from "../../hooks/tenantAdminHooks";
import { ApiClientError } from "../../lib/api";
import { messageForCode } from "../../lib/messages";

const field = { display: "block", width: "100%", padding: 8,
  marginBottom: "var(--spacing)", borderRadius: "var(--radius)",
  border: "1px solid var(--color-text-muted)" } as const;

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

  return (
    <main style={{ padding: 24, maxWidth: 820, margin: "0 auto" }}>
      <Link to="/tenant" style={{ color: "var(--color-primary)" }}>← Dashboard</Link>
      <h1 style={{ color: "var(--color-primary)" }}>Facilities</h1>

      {isLoading && <p>Loading…</p>}
      <div style={{ display: "grid", gap: "var(--spacing)", marginBottom: 24 }}>
        {facilities?.items.filter((f) => f.active).map((f) => (
          <div key={f.id} style={{ padding: 16, borderRadius: "var(--radius)",
            border: "1px solid var(--color-text-muted)", background: "var(--color-surface)",
            display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong>{f.name}</strong>
              <div style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
                {f.sport} · {f.open_time}–{f.close_time} · {f.slot_duration_minutes}min
                {f.description ? ` · ${f.description}` : ""}
              </div>
            </div>
            <button onClick={() => deactivate.mutate(f.id)} style={{ padding: "6px 12px",
              borderRadius: "var(--radius)", border: "1px solid var(--color-danger)",
              color: "var(--color-danger)", background: "transparent", cursor: "pointer" }}>
              Remove
            </button>
          </div>
        ))}
      </div>

      <h2>Add a facility</h2>
      <form onSubmit={submit} style={{ maxWidth: 480 }}>
        <label>Type</label>
        <select style={field} value={typeId} onChange={(e) => setTypeId(e.target.value)}>
          <option value="">Select a type…</option>
          {catalog?.items.map((c) => (
            <option key={c.type_id} value={c.type_id}>{c.name}</option>
          ))}
        </select>
        <label>Name</label>
        <input style={field} value={name} onChange={(e) => setName(e.target.value)}
          placeholder="North Side Court" required />
        <label>Opens</label>
        <input style={field} value={openTime} onChange={(e) => setOpenTime(e.target.value)}
          placeholder="06:00" required />
        <label>Closes</label>
        <input style={field} value={closeTime} onChange={(e) => setCloseTime(e.target.value)}
          placeholder="22:00" required />
        <label>Slot duration (minutes)</label>
        <input style={field} type="number" value={duration}
          onChange={(e) => setDuration(Number(e.target.value))} required />
        <label>Description (optional)</label>
        <input style={field} value={description}
          onChange={(e) => setDescription(e.target.value)} />
        <button type="submit" disabled={createFacility.isPending} style={{ width: "100%",
          padding: 10, background: "var(--color-primary)", color: "#fff", border: "none",
          borderRadius: "var(--radius)", cursor: "pointer" }}>
          {createFacility.isPending ? "Creating…" : "Add facility"}
        </button>
      </form>
      {error && <p style={{ color: "var(--color-danger)" }}>{error}</p>}
      {ok && <p style={{ color: "var(--color-secondary)" }}>{ok}</p>}
    </main>
  );
}
