import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function PlatformRoute({ children }: { children: ReactNode }) {
  const { user, claims, loading } = useAuth();
  if (loading) return <p style={{ padding: 24 }}>Loading…</p>;
  if (!user) return <Navigate to="/signin" replace />;
  if (claims?.role !== "platform_admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}
