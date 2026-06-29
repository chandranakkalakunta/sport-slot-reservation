import { Outlet } from "react-router-dom";

import { SlotSenseWordmark } from "./SlotSenseWordmark";

/** Layout wrapper for all authenticated routes. Renders page content via Outlet,
 *  then appends the "powered by SlotSense" footer. Auth pages (SignIn, ForgotPassword,
 *  ResetPassword, ForcePasswordChange) are NOT wrapped here — footer omitted there. */
export function AuthedLayout() {
  return (
    <>
      <Outlet />
      <footer className="mt-8 py-4 border-t border-border">
        <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
          powered by{" "}
          <SlotSenseWordmark className="text-xs text-muted-foreground" />
        </p>
      </footer>
    </>
  );
}
