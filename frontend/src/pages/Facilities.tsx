import { Bot } from "lucide-react";
import { Link } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { useFacilities } from "../hooks/bookingHooks";

export default function Facilities() {
  const { data, isLoading, error } = useFacilities();

  const activeFacilities = data?.items.filter((f) => f.active) ?? [];

  return (
    <>
      <AppHeader>
        <Button asChild variant="outline" size="sm">
          <Link to="/bookings" style={{ textDecoration: "none" }}>My bookings</Link>
        </Button>
      </AppHeader>

      <main className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        <h1 className="text-2xl font-semibold text-foreground">Facilities</h1>

        {/* Loading / error / empty states */}
        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading facilities…</p>
        )}
        {error && (
          <p className="text-sm text-destructive">Couldn't load facilities.</p>
        )}
        {!isLoading && !error && data && activeFacilities.length === 0 && (
          <p className="text-sm text-muted-foreground">No facilities available.</p>
        )}

        {/* Booking Assistant promo */}
        <Link
          to="/assistant"
          className="block rounded-lg border border-primary/40 bg-surface p-4 no-underline hover:bg-accent transition-colors"
          style={{ textDecoration: "none" }}
        >
          <p className="font-semibold text-primary text-sm flex items-center gap-1.5">
            <Bot className="size-4 shrink-0" />
            Booking Assistant
          </p>
          <p className="text-muted-foreground text-xs mt-1">
            Try &ldquo;book my usual tennis slot&rdquo; or &ldquo;is tennis free tomorrow?&rdquo;
          </p>
          <p className="text-primary text-xs mt-1.5">Open assistant →</p>
        </Link>

        {/* Facility list */}
        <div className="grid gap-3">
          {activeFacilities.map((f) => (
            <Card key={f.id} className="hover:bg-accent transition-colors py-0">
              <CardContent className="p-0">
                <Link
                  to={`/facilities/${f.id}`}
                  className="block p-4 no-underline text-foreground"
                  style={{ textDecoration: "none" }}
                >
                  <p className="font-semibold text-foreground">{f.name}</p>
                  <p className="text-sm text-muted-foreground tabular-nums mt-0.5">
                    {f.sport} · {f.open_time}–{f.close_time} · {f.slot_duration_minutes}min
                  </p>
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </>
  );
}
