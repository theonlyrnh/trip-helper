import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Trips from "./pages/Trips";
import TripWorkspace from "./pages/TripWorkspace";
import DashboardPage from "./pages/DashboardPage";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="trips" element={<Trips />} />
        <Route path="workspace/:tripId?" element={<TripWorkspace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
