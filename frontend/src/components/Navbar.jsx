import { Link, NavLink, useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/dashboard", label: "Dashboard", auth: true },
  { to: "/analysis", label: "Analysis", auth: true },
  { to: "/compare", label: "Compare", auth: true },
  { to: "/history", label: "History", auth: true },
  { to: "/settings", label: "Settings", auth: true },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <header className="sticky top-0 z-30 backdrop-blur-md" data-testid="navbar">
      <div className="page-shell flex items-center justify-between py-4">
        <Link to="/" className="flex items-center gap-3" data-testid="brand-link">
          <span className="brand-mark">CP</span>
          <div>
            <div className="font-semibold tracking-wide">CricPose AI Pro</div>
            <div className="text-xs muted">Bowling action intelligence</div>
          </div>
        </Link>
        <nav className="hidden md:flex items-center gap-1">
          {LINKS.filter((l) => !l.auth || user).map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              data-testid={`nav-${link.label.toLowerCase()}`}
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive ? "text-[var(--text)] bg-[rgba(87,240,255,0.08)]" : "muted hover:text-white"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          {user ? (
            <>
              <div className="hidden sm:block text-right">
                <div className="text-sm font-medium">{user.full_name}</div>
                <div className="text-xs muted">{user.email}</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="btn-outline-brand"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" /> Logout
              </Button>
            </>
          ) : (
            <>
              <Link to="/login" data-testid="login-link">
                <Button variant="outline" className="btn-outline-brand" size="sm">
                  Login
                </Button>
              </Link>
              <Link to="/signup" data-testid="signup-link">
                <Button className="btn-brand" size="sm">
                  Create account
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
