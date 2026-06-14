import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { usePasswordGate } from "./usePasswordGate";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const { mustChange, loading: pwLoading } = usePasswordGate();
  if (loading) return <p style={{ padding: "24px" }}>Loading…</p>;
  if (!user) return <Navigate to="/signin" replace />;
  if (pwLoading) return <p style={{ padding: "24px" }}>Loading…</p>;
  if (mustChange) return <Navigate to="/force-password" replace />;
  return <>{children}</>;
}
