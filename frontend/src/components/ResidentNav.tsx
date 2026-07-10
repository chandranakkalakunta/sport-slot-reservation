import { Link } from "react-router-dom";

import { Button } from "./ui/button";

// Shared AppHeader nav for resident-facing pages (Facilities, Assistant,
// MyBookings) — all three links always visible so none is a dead end.
export function ResidentNav() {
  return (
    <>
      <Button asChild variant="outline" size="sm">
        <Link to="/" style={{ textDecoration: "none" }}>Facilities</Link>
      </Button>
      <Button asChild variant="outline" size="sm">
        <Link to="/bookings" style={{ textDecoration: "none" }}>My bookings</Link>
      </Button>
      <Button asChild variant="outline" size="sm">
        <Link to="/invoices" style={{ textDecoration: "none" }}>Invoices</Link>
      </Button>
    </>
  );
}
