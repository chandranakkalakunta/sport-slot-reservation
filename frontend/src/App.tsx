import { useQuery } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { PlatformRoute } from "./auth/PlatformRoute";
import { ProtectedRoute } from "./auth/ProtectedRoute";
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

/** Role-based landing: platform_admin → /admin; must_change_password → /force-password;
 *  otherwise the resident Facilities view. */
function Landing() {
  const { claims } = useAuth();
  const isAdmin = claims?.role === "platform_admin";
  const { data } = useQuery({
    queryKey: ["profile"],
    queryFn: () => apiFetch<{ must_change_password?: boolean }>("/users/me"),
    enabled: !isAdmin,
  });
  if (isAdmin) return <Navigate to="/admin" replace />;
  if (data?.must_change_password) return <Navigate to="/force-password" replace />;
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
      </Routes>
    </AuthProvider>
  );
}
