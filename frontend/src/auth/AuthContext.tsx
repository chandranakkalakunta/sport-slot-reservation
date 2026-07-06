import {
  GoogleAuthProvider,
  onIdTokenChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut as fbSignOut,
  type User,
} from "firebase/auth";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { loadBrandingForSlug } from "../lib/branding";
import { auth } from "../lib/firebase";

const _APEX = "slotsense.chandraailabs.com";

/**
 * Mirrors the backend's `_slug_from_host` three-way logic (ADR-0007):
 *   exact apex → "" (recognized SlotSense host, no tenant)
 *   {x}.apex   → "{x}" (tenant subdomain)
 *   anything else (localhost, *.web.app, *.run.app, unknown) → null (skip check)
 */
export function slugFromHost(hostname: string): string | null {
  if (hostname === _APEX) return "";
  if (hostname.endsWith(`.${_APEX}`)) return hostname.slice(0, hostname.length - _APEX.length - 1);
  return null;
}

interface AuthState {
  user: User | null;
  idToken: string | null;
  claims: Record<string, unknown> | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [idToken, setIdToken] = useState<string | null>(null);
  const [claims, setClaims] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // onIdTokenChanged (not onAuthStateChanged) fires on refresh too,
    // keeping the attached token fresh automatically.
    return onIdTokenChanged(auth, async (u) => {
      setUser(u);
      if (u) {
        const result = await u.getIdTokenResult();
        setIdToken(result.token);
        setClaims(result.claims);

        // Mismatch check: if the current host's slug differs from the token's
        // tenant_slug, sign out and hard-navigate to the correct subdomain.
        // Skips for platform_admin (no tenant_slug) and non-SlotSense hosts
        // (null → local dev / *.web.app / *.run.app).
        const hostSlug = slugFromHost(window.location.hostname);
        if (result.claims.role !== "platform_admin" && hostSlug !== null) {
          const claimSlug = result.claims.tenant_slug;
          if (hostSlug !== claimSlug) {
            await fbSignOut(auth);
            window.location.href = `https://${claimSlug}.${_APEX}/signin?redirected=1`;
            return;
          }
        }

        const slug = result.claims.tenant_slug;
        if (typeof slug === "string") {
          void loadBrandingForSlug(slug);
        }
      } else {
        setIdToken(null);
        setClaims(null);
      }
      setLoading(false);
    });
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      idToken,
      claims,
      loading,
      signIn: async (email, password) => {
        await signInWithEmailAndPassword(auth, email, password);
      },
      signInWithGoogle: async () => {
        await signInWithPopup(auth, new GoogleAuthProvider());
      },
      signOut: async () => {
        await fbSignOut(auth);
      },
    }),
    [user, idToken, claims, loading],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
