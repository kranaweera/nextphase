import { NavLink, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="app-shell">
      <header className="nav-bar">
        <span className="brand">NextPhase</span>
        <nav>
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Overview
          </NavLink>
          <NavLink to="/alerts" className={({ isActive }) => (isActive ? "active" : "")}>
            Alerts
          </NavLink>
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
