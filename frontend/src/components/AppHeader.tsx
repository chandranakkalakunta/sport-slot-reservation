import { useState } from "react";
import { LogOut, Menu, Moon, Sun, X } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { getLastBranding } from "../lib/branding";
import { applyMode, getActiveMode, type ThemeMode } from "../lib/themeMode";
import { Button } from "./ui/button";

export function AppHeader({ children }: { children?: React.ReactNode }) {
  const { user, claims, signOut } = useAuth();
  const branding = getLastBranding();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mode, setMode] = useState<ThemeMode>(getActiveMode);

  const role = claims?.role ?? "";
  const roleLabel =
    role === "platform_admin" ? "Platform admin"
    : role === "tenant_admin" ? "Tenant admin"
    : role === "resident" ? "Resident"
    : role;

  function toggleMode() {
    const next: ThemeMode = mode === "dark" ? "light" : "dark";
    applyMode(next);
    setMode(next);
  }

  return (
    <header className="border-b border-border">
      {/* Top bar — always visible */}
      <div className="flex items-center justify-between gap-2 px-4 py-3">
        {/* Brand */}
        <div className="flex items-center gap-3 min-w-0">
          {branding?.brand_logo_url && (
            <img src={branding.brand_logo_url} alt="" className="h-8 shrink-0 max-w-[80px] object-contain" />
          )}
          <Link
            to="/"
            className="text-xl font-bold text-primary truncate"
            style={{ textDecoration: "none" }}
          >
            {branding?.brand_name || "SportSlot"}
          </Link>
        </div>

        {/* Desktop nav: inject caller-supplied nav items */}
        <nav
          aria-label="Main navigation"
          className="hidden sm:flex flex-1 items-center gap-2 px-4"
        >
          {children}
        </nav>

        {/* Right cluster */}
        <div className="flex items-center gap-2 shrink-0">
          {user && (
            <span className="hidden sm:inline text-sm text-muted-foreground">
              {user.email}
              {roleLabel ? ` · ${roleLabel}` : ""}
            </span>
          )}

          {/* Dark-mode toggle — desktop header only; mobile version lives in the hamburger menu */}
          <Button
            variant="ghost"
            size="icon"
            className="hidden sm:inline-flex"
            onClick={toggleMode}
            aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {mode === "dark" ? (
              <Sun className="size-4" />
            ) : (
              <Moon className="size-4" />
            )}
          </Button>

          {/* Desktop-only: Account + Sign out */}
          <Button
            asChild
            variant="outline"
            size="sm"
            className="hidden sm:inline-flex"
          >
            <Link to="/account" style={{ textDecoration: "none" }}>Account</Link>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="hidden sm:inline-flex"
            onClick={() => signOut()}
          >
            <LogOut />
            Sign out
          </Button>

          {/* Mobile-only: hamburger */}
          <Button
            variant="ghost"
            size="icon"
            className="sm:hidden min-h-[44px] min-w-[44px]"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile menu — rendered only when open */}
      {menuOpen && (
        <nav
          aria-label="Mobile navigation"
          className="sm:hidden flex flex-col gap-3 border-t border-border px-4 py-4"
        >
          {children}

          {/* Dark-mode toggle as a menu item — mobile only; mirrors header toggle behavior */}
          <Button
            variant="ghost"
            size="sm"
            className="min-h-[44px] justify-start gap-2"
            onClick={toggleMode}
            aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {mode === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            {mode === "dark" ? "Light mode" : "Dark mode"}
          </Button>

          {user && (
            <span className="text-sm text-muted-foreground">
              {user.email}
              {roleLabel ? ` · ${roleLabel}` : ""}
            </span>
          )}

          <Button
            asChild
            variant="outline"
            size="sm"
            className="min-h-[44px] justify-start"
          >
            <Link to="/account" style={{ textDecoration: "none" }}>Account</Link>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="min-h-[44px] justify-start"
            onClick={() => signOut()}
          >
            <LogOut />
            Sign out
          </Button>
        </nav>
      )}
    </header>
  );
}
