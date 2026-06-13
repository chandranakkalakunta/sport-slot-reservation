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
