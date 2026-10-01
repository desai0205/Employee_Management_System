import { Navigate, NavLink, Outlet } from "react-router-dom";
import { useAuth, canReadAudit } from "../auth";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/employees", label: "Employees" },
  { to: "/departments", label: "Departments" },
  { to: "/attendance", label: "Attendance" },
  { to: "/leaves", label: "Leave" },
  { to: "/reports", label: "Reports" },
];

export function RequireAuth() {
  const { me, ready } = useAuth();
  if (!ready) return <p className="loading">Loading your session</p>;
  if (!me) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function Layout() {
  const { me, logout } = useAuth();
  if (!me) return null;
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span>People</span>
          <strong>Roster</strong>
        </div>
        <nav>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className={({ isActive }) => (isActive ? "active" : "")}>
              {link.label}
            </NavLink>
          ))}
          {canReadAudit(me.role) ? (
            <NavLink to="/audit" className={({ isActive }) => (isActive ? "active" : "")}>
              Audit
            </NavLink>
          ) : null}
          <NavLink to="/account" className={({ isActive }) => (isActive ? "active" : "")}>
            Account
          </NavLink>
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">{me.role}</p>
            <p className="who">{me.email}</p>
          </div>
          <button type="button" className="ghost" onClick={() => void logout()}>
            Sign out
          </button>
        </header>
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
