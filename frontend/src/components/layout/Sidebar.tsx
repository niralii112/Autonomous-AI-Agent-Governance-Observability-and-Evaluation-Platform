import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { isDemoMode } from "../../demoMode";
import "./Sidebar.css";

const primary = [
  ["Overview", "/"],
  ["AI Assistants", "/agents"],
  ["Activity History", "/actions"],
  ["Approvals", "/approvals"],
];

const oversight = [
  ["Safety Rules", "/policies"],
  ["AI Decisions", "/governance"],
  ["Risk & Safety", "/risk"],
  ["AI Performance", "/evaluations"],
  ["Audit History", "/audit"],
];

const technical = [
  ["Tools", "/tools"],
  ["Trace Explorer", "/traces"],
  ["System Health", "/settings"],
];

function NavigationLinks({ items }: { items: string[][] }) {
  return items.map(([label, path]) => (
    <NavLink key={path} to={path} end={path === "/"}>
      {label}
    </NavLink>
  ));
}

export default function Sidebar() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();
  const isTechnicalPage = technical.some(([, path]) =>
    pathname === path || pathname.startsWith(path + "/"),
  );

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <strong>AgentGuard</strong>
        {isDemoMode && <span>Demo workspace</span>}
      </div>
      <nav aria-label="Workspace navigation">
        <NavigationLinks items={primary} />
        <div className="sidebar-secondary">
          <p>Oversight</p>
          <NavigationLinks items={oversight} />
        </div>
        <details key={String(isTechnicalPage)} open={isTechnicalPage}>
          <summary>Technical details</summary>
          <NavigationLinks items={technical} />
        </details>
      </nav>
      <div className="sidebar-account">
        <span>{user?.username}</span>
        <button type="button" onClick={() => void signOut().catch(console.error)}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
