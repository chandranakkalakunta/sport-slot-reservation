import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { PlatformRoute } from "./auth/PlatformRoute";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { TenantAdminRoute } from "./auth/TenantAdminRoute";
import { useAuth } from "./auth/AuthContext";
import { apiFetch } from "./lib/api";
import Facilities from "./pages/Facilities";
import FacilityAvailability from "./pages/FacilityAvailability";
import ForcePasswordChange from "./pages/ForcePasswordChange";
import MyBookings from "./pages/MyBookings";
import SignIn from "./pages/SignIn";
import CreateTenant from "./pages/admin/CreateTenant";
import CreateUser from "./pages/admin/CreateUser";
import TenantList from "./pages/admin/TenantList";
import TenantBranding from "./pages/tenant/TenantBranding";
import TenantDashboard from "./pages/tenant/TenantDashboard";
import TenantFacilities from "./pages/tenant/TenantFacilities";
import TenantPolicies from "./pages/tenant/TenantPolicies";
import TenantUsers from "./pages/tenant/TenantUsers";

/** Role-based landing: platform_admin → /admin first (seeded clean, own profile path).
 *  Everyone else: fetch /users/me — must_change_password gates BEFORE the role redirect
 *  so tenant admins with a forced reset are not skipped to /tenant. */
function Landing() {
  const { claims } = useAuth();
  const isAdmin = claims?.role === "platform_admin";
  const isTenantAdmin = claims?.role === "tenant_admin";
  const { data, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: () => apiFetch<{ must_change_password?: boolean }>("/users/me"),
    enabled: !isAdmin,   // run for tenant_admin + resident; platform_admin profile is elsewhere
  });
  // Platform admin: seeded clean, own profile path → straight to /admin.
  if (isAdmin) return <Navigate to="/admin" replace />;
  // Everyone else: wait for the profile flag before redirecting.
  if (isLoading) return <p>Loading…</p>;
  // Forced password change gates BEFORE the role landing.
  if (data?.must_change_password) return <Navigate to="/force-password" replace />;
  if (isTenantAdmin) return <Navigate to="/tenant" replace />;
  return <Facilities />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/signin" element={<SignIn />} />
        <Route path="/" element={<ProtectedRoute><Landing /></ProtectedRoute>} />
        <Route path="/facilities/:facilityId"
          element={<ProtectedRoute><FacilityAvailability /></ProtectedRoute>} />
        <Route path="/bookings"
          element={<ProtectedRoute><MyBookings /></ProtectedRoute>} />
        <Route path="/force-password" element={<ForcePasswordChange />} />
        <Route path="/admin" element={<PlatformRoute><TenantList /></PlatformRoute>} />
        <Route path="/admin/tenants/new" element={<PlatformRoute><CreateTenant /></PlatformRoute>} />
        <Route path="/admin/tenants/:tenantId/users/new" element={<PlatformRoute><CreateUser /></PlatformRoute>} />
        <Route path="/tenant" element={<TenantAdminRoute><TenantDashboard /></TenantAdminRoute>} />
        <Route path="/tenant/facilities" element={<TenantAdminRoute><TenantFacilities /></TenantAdminRoute>} />
        <Route path="/tenant/branding" element={<TenantAdminRoute><TenantBranding /></TenantAdminRoute>} />
        <Route path="/tenant/policies" element={<TenantAdminRoute><TenantPolicies /></TenantAdminRoute>} />
        <Route path="/tenant/users" element={<TenantAdminRoute><TenantUsers /></TenantAdminRoute>} />
      </Routes>
    </AuthProvider>
  );
}
