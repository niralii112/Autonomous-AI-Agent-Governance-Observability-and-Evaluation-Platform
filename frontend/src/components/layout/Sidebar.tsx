import { NavLink } from "react-router-dom";
import "./Sidebar.css";

const navigationSections = [
  {
    category: "Operations",
    items: [
      { label: "Dashboard", path: "/" },
      { label: "Agents", path: "/agents" },
      { label: "Actions", path: "/actions" },
      { label: "Approvals", path: "/approvals" },
    ],
  },
  {
    category: "Governance",
    items: [
      { label: "Policies", path: "/policies" },
      { label: "Decisions", path: "/governance" },
      { label: "Tools", path: "/tools" },
      { label: "Risk Analytics", path: "/risk" },
    ],
  },
  {
    category: "Observability",
    items: [
      { label: "Trace Explorer", path: "/traces" },
      { label: "Evaluations", path: "/evaluations" },
      { label: "Audit Log", path: "/audit" },
      { label: "System Health", path: "/settings" },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="mb-6">
        <h2 className="sidebar-title">Agent Governance</h2>
        <span className="text-[10px] font-black uppercase tracking-[0.25em] text-[#777777] block -mt-8 mb-4">
          v1.0.0 Control
        </span>
      </div>

      <nav className="sidebar-nav space-y-6">
        {navigationSections.map((section) => (
          <div key={section.category}>
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#888888] px-4 mb-2 block">
              {section.category}
            </span>
            <div className="space-y-1">
              {section.items.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "/"}
                  className={({ isActive }) =>
                    isActive ? "sidebar-link active" : "sidebar-link"
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}