import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  AppWindow,
  BookOpen,
  BriefcaseBusiness,
  Crosshair,
  Inbox,
  LayoutDashboard,
  Menu,
  Moon,
  PlugZap,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  Telescope,
  X,
} from "lucide-react";
import { useApi } from "../api/useApi";
import { useTheme } from "./Theme";
import { CommandPalette } from "./CommandPalette";
import type { Health } from "../types/api";

const navigation = [
  {
    caption: "Workspace",
    items: [
      { to: "/", label: "Today", icon: LayoutDashboard, end: true },
      { to: "/inbox", label: "Inbox", icon: Inbox },
      { to: "/search", label: "Search", icon: Search },
      { to: "/books", label: "Books", icon: BookOpen },
      { to: "/projects", label: "Projects", icon: Crosshair },
      { to: "/activity", label: "Activity", icon: Activity },
    ],
  },
  {
    caption: "Engines",
    items: [
      { to: "/next", label: "Next", icon: Telescope },
      { to: "/work", label: "Work", icon: BriefcaseBusiness },
      { to: "/cocoder", label: "CoCoder", icon: ShieldCheck },
    ],
  },
  {
    caption: "System",
    items: [
      { to: "/applications", label: "Applications", icon: AppWindow },
      { to: "/integrations", label: "Integrations", icon: PlugZap },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Layout() {
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { theme, toggle } = useTheme();
  const health = useApi<Health>("/api/health", { pollMs: 30000 });

  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((current) => !current);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const online = Boolean(health.data && health.data.status === "ok");

  return (
    <div className={`app-shell ${menuOpen ? "menu-open" : ""}`}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <Crosshair size={21} strokeWidth={1.7} />
          </div>
          <div className="brand-copy">
            <strong>Mission Control</strong>
            <span>Applied AI workspace</span>
          </div>
          <button
            className="icon-button mobile-only"
            aria-label="Close navigation"
            onClick={() => setMenuOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <button className="command-trigger" onClick={() => setPaletteOpen(true)}>
          <Search size={15} />
          <span>Search or command</span>
          <kbd>Ctrl K</kbd>
        </button>

        <nav className="nav">
          {navigation.map((group) => (
            <div className="nav-group" key={group.caption}>
              <span className="nav-caption">{group.caption}</span>
              {group.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
                >
                  <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="system-row">
            <span className={`status-dot status-${online ? "running" : "unavailable"}`} />
            <span>{online ? "Local system online" : "Backend unreachable"}</span>
          </div>
          <div className="system-meta">
            <span>{health.data ? `v${health.data.version}` : "No connection"}</span>
            <span>{health.data?.ai_enabled ? "AI advisory on" : "AI advisory off"}</span>
          </div>
          <button className="theme-toggle" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
            {theme === "dark" ? "Light theme" : "Dark theme"}
          </button>
        </div>
      </aside>

      <div className="mobile-bar">
        <button className="icon-button" onClick={() => setMenuOpen(true)} aria-label="Open navigation">
          <Menu size={19} />
        </button>
        <span className="mobile-brand">Mission Control</span>
        <button className="icon-button" onClick={() => setPaletteOpen(true)} aria-label="Search or command">
          <Search size={18} />
        </button>
        <span className={`status-dot status-${online ? "running" : "unavailable"}`} aria-hidden="true" />
      </div>

      <main className="main-content" id="main-content">
        <Outlet />
      </main>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
