import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/AuthContext";
import { PlatformRoute } from "./auth/PlatformRoute";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { TenantAdminRoute } from "./auth/TenantAdminRoute";
import { AuthedLayout } from "./components/AuthedLayout";
import Account from "./pages/Account";
import Assistant from "./pages/Assistant";
import Facilities from "./pages/Facilities";
import FacilityAvailability from "./pages/FacilityAvailability";
import ForgotPassword from "./pages/ForgotPassword";
import ForcePasswordChange from "./pages/ForcePasswordChange";
import MyBookings from "./pages/MyBookings";
import ResetPassword from "./pages/ResetPassword";
import SignIn from "./pages/SignIn";
import CreateTenant from "./pages/admin/CreateTenant";
import CreateUser from "./pages/admin/CreateUser";
import TenantList from "./pages/admin/TenantList";
import TenantBranding from "./pages/tenant/TenantBranding";
import TenantDailyOverview from "./pages/tenant/TenantDailyOverview";
import TenantDashboard from "./pages/tenant/TenantDashboard";
import TenantFacilities from "./pages/tenant/TenantFacilities";
import TenantPolicies from "./pages/tenant/TenantPolicies";
import TenantUsers from "./pages/tenant/TenantUsers";

/** Role-based landing: gate is handled by ProtectedRoute before Landing renders.
 *  Just route by role. */
function Landing() {
  const { claims } = useAuth();
  if (claims?.role === "platform_admin") return <Navigate to="/admin" replace />;
  if (claims?.role === "tenant_admin") return <Navigate to="/tenant" replace />;
  return <Facilities />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Auth pages — no footer */}
        <Route path="/signin" element={<SignIn />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset" element={<ResetPassword />} />
        <Route path="/force-password" element={<ForcePasswordChange />} />

        {/* Authed pages — footer via AuthedLayout */}
        <Route element={<AuthedLayout />}>
          <Route path="/" element={<ProtectedRoute><Landing /></ProtectedRoute>} />
          <Route path="/facilities/:facilityId"
            element={<ProtectedRoute><FacilityAvailability /></ProtectedRoute>} />
          <Route path="/bookings"
            element={<ProtectedRoute><MyBookings /></ProtectedRoute>} />
          <Route path="/account"
            element={<ProtectedRoute><Account /></ProtectedRoute>} />
          <Route path="/assistant"
            element={<ProtectedRoute><Assistant /></ProtectedRoute>} />
          <Route path="/admin" element={<PlatformRoute><TenantList /></PlatformRoute>} />
          <Route path="/admin/tenants/new" element={<PlatformRoute><CreateTenant /></PlatformRoute>} />
          <Route path="/admin/tenants/:tenantId/users/new" element={<PlatformRoute><CreateUser /></PlatformRoute>} />
          <Route path="/tenant" element={<TenantAdminRoute><TenantDashboard /></TenantAdminRoute>} />
          <Route path="/tenant/facilities" element={<TenantAdminRoute><TenantFacilities /></TenantAdminRoute>} />
          <Route path="/tenant/branding" element={<TenantAdminRoute><TenantBranding /></TenantAdminRoute>} />
          <Route path="/tenant/policies" element={<TenantAdminRoute><TenantPolicies /></TenantAdminRoute>} />
          <Route path="/tenant/users" element={<TenantAdminRoute><TenantUsers /></TenantAdminRoute>} />
          <Route path="/tenant/overview" element={<TenantAdminRoute><TenantDailyOverview /></TenantAdminRoute>} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
