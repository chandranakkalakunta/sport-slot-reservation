import { Outlet } from "react-router-dom";

import { SlotSenseWordmark } from "./SlotSenseWordmark";

/** Layout wrapper for all authenticated routes.
 *  Footer is fixed to the viewport bottom so it is always visible on both
 *  short pages and long scrolling pages. pb-14 on the content wrapper ensures
 *  the last list item is never hidden behind the fixed footer (~50px tall).
 *  Auth pages (SignIn, ForgotPassword, ResetPassword, ForcePasswordChange) are
 *  NOT wrapped here — footer omitted there. */
export function AuthedLayout() {
  return (
    <>
      <div className="pb-14">
        <Outlet />
      </div>
      <footer className="fixed bottom-0 left-0 right-0 z-10 border-t border-border bg-background py-3">
        <p className="flex items-center justify-center gap-1 text-xs text-muted-foreground">
          powered by{" "}
          <SlotSenseWordmark className="text-xs text-muted-foreground" />
        </p>
      </footer>
    </>
  );
}
