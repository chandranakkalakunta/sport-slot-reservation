import { Outlet } from "react-router-dom";

import { SlotSenseWordmark } from "./SlotSenseWordmark";

/** Layout wrapper for all authenticated routes. Renders page content via Outlet,
 *  then sticks the "powered by SlotSense" footer to the viewport bottom.
 *  Auth pages (SignIn, ForgotPassword, ResetPassword, ForcePasswordChange) are
 *  NOT wrapped here — footer omitted there. */
export function AuthedLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex-1">
        <Outlet />
      </div>
      <footer className="py-4 border-t border-border">
        <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
          powered by{" "}
          <SlotSenseWordmark className="text-xs text-muted-foreground" />
        </p>
      </footer>
    </div>
  );
}
