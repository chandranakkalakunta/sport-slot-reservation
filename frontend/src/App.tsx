import { Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import Facilities from "./pages/Facilities";
import FacilityAvailability from "./pages/FacilityAvailability";
import SignIn from "./pages/SignIn";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/signin" element={<SignIn />} />
        <Route path="/" element={<ProtectedRoute><Facilities /></ProtectedRoute>} />
        <Route path="/facilities/:facilityId"
          element={<ProtectedRoute><FacilityAvailability /></ProtectedRoute>} />
      </Routes>
    </AuthProvider>
  );
}
