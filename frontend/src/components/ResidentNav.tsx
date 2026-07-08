import { Link } from "react-router-dom";

import { Button } from "./ui/button";

// Shared AppHeader nav for resident-facing pages (Facilities, Assistant,
// MyBookings) — both links always visible so neither is a dead end.
export function ResidentNav() {
  return (
    <>
      <Button asChild variant="outline" size="sm">
        <Link to="/" style={{ textDecoration: "none" }}>Facilities</Link>
      </Button>
      <Button asChild variant="outline" size="sm">
        <Link to="/bookings" style={{ textDecoration: "none" }}>My bookings</Link>
      </Button>
    </>
  );
}
