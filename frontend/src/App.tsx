import "./App.css";

import {
  BrowserRouter,
  Routes,
  Route,
  Outlet,
} from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import Agents from "./pages/Agents";
import AgentDetails from "./pages/AgentDetails";
import Governance from "./pages/Governance";
import Policies from "./pages/Policies";
import Approvals from "./pages/Approvals";
import Actions from "./pages/Actions";
import ActionDetailsPage from "./pages/ActionDetailsPage";
import Tools from "./pages/Tools";
import Risk from "./pages/Risk";
import Traces from "./pages/Traces";
import TraceDetailsPage from "./pages/TraceDetailsPage";
import Evaluations from "./pages/Evaluations";
import Audit from "./pages/Audit";
import Settings from "./pages/Settings";
import NotFound from "./pages/NotFound";

import Login from "./pages/Login";
import ProtectedRoute from "./auth/ProtectedRoute";
import Sidebar from "./components/layout/Sidebar";
import ErrorBoundary from "./components/common/ErrorBoundary";

function DashboardLayout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />

      <main style={{ flex: 1, minWidth: 0 }}>
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public login page */}
        <Route path="/login" element={<Login />} />

        {/* Protected platform routes */}
        <Route element={<ProtectedRoute />}>
          <Route element={<DashboardLayout />}>
            {/* Screen 2: Overview Dashboard */}
            <Route path="/" element={<Dashboard />} />

            {/* Screen 3: Agent Management & Detail */}
            <Route path="/agents" element={<Agents />} />
            <Route path="/agents/:agentId" element={<AgentDetails />} />

            {/* Screen 4: Tool Management */}
            <Route path="/tools" element={<Tools />} />

            {/* Screen 5: Policy Management & Decisions */}
            <Route path="/policies" element={<Policies />} />
            <Route path="/governance" element={<Governance />} />

            {/* Screens 6 & 7: Actions History & Details */}
            <Route path="/actions" element={<Actions />} />
            <Route path="/actions/:actionId" element={<ActionDetailsPage />} />

            {/* Screen 8: Approval Queue (ADMIN / REVIEWER / OPERATOR) */}
            <Route path="/approvals" element={<Approvals />} />

            {/* Screen 9: Risk Analytics */}
            <Route path="/risk" element={<Risk />} />

            {/* Screen 10: Trace Explorer & Waterfall Detail */}
            <Route path="/traces" element={<Traces />} />
            <Route path="/traces/:traceId" element={<TraceDetailsPage />} />

            {/* Screen 11: Evaluation Analytics (support both singular and plural) */}
            <Route path="/evaluations" element={<Evaluations />} />
            <Route path="/evaluation" element={<Evaluations />} />

            {/* Screen 12: Audit Log */}
            <Route path="/audit" element={<Audit />} />

            {/* Screen 13: Settings & System Health */}
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>

        {/* 404 Not Found route */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}
