import { LogOut } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { getLastBranding } from "../lib/branding";
import { Button } from "./ui/button";

export function AppHeader({ children }: { children?: React.ReactNode }) {
  const { user, claims, signOut } = useAuth();
  const branding = getLastBranding();
  const role = claims?.role ?? "";
  const roleLabel = role === "platform_admin" ? "Platform admin"
    : role === "tenant_admin" ? "Tenant admin"
    : role === "resident" ? "Resident" : role;

  return (
    <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-6 py-3">
      <div className="flex items-center gap-3">
        {branding?.brand_logo_url && (
          <img src={branding.brand_logo_url} alt="" className="h-8" />
        )}
        <Link
          to="/"
          className="text-xl font-bold text-primary no-underline"
          style={{ textDecoration: "none" }}
        >
          {branding?.brand_name || "SportSlot"}
        </Link>
        {children}
      </div>
      <div className="flex items-center gap-2">
        {user && (
          <span className="text-sm text-muted-foreground">
            {user.email}{roleLabel ? ` · ${roleLabel}` : ""}
          </span>
        )}
        <Button asChild variant="outline" size="sm">
          <Link to="/account" style={{ textDecoration: "none" }}>Account</Link>
        </Button>
        <Button variant="ghost" size="sm" onClick={() => signOut()}>
          <LogOut />
          Sign out
        </Button>
      </div>
    </header>
  );
}
