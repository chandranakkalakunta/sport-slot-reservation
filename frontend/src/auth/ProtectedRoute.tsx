import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <p style={{ padding: "24px" }}>Loading…</p>;
  if (!user) return <Navigate to="/signin" replace />;
  return <>{children}</>;
}
