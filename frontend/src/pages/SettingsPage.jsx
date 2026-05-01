import AppShell from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { useNavigate } from "react-router-dom";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <AppShell eyebrow="Settings" title="Your account" description="Manage your CricPose AI Pro profile and session.">
      <div className="panel" data-testid="account-panel">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="stat-card">
            <div className="text-xs uppercase tracking-[0.18em] muted">Full name</div>
            <div className="font-semibold mt-1">{user?.full_name}</div>
          </div>
          <div className="stat-card">
            <div className="text-xs uppercase tracking-[0.18em] muted">Email</div>
            <div className="font-semibold mt-1">{user?.email}</div>
          </div>
          <div className="stat-card">
            <div className="text-xs uppercase tracking-[0.18em] muted">Role</div>
            <div className="font-semibold mt-1 capitalize">{user?.role}</div>
          </div>
          <div className="stat-card">
            <div className="text-xs uppercase tracking-[0.18em] muted">Member since</div>
            <div className="font-semibold mt-1">
              {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
            </div>
          </div>
        </div>
        <div className="mt-5">
          <Button
            variant="outline"
            className="btn-outline-brand"
            onClick={async () => {
              await logout();
              navigate("/");
            }}
            data-testid="settings-logout-btn"
          >
            Sign out
          </Button>
        </div>
      </div>

      <div className="panel" data-testid="estimation-panel">
        <h3 className="font-semibold mb-2">About the estimates</h3>
        <ul className="flex flex-col gap-2 muted text-sm">
          <li>
            • Pose landmarks come from MediaPipe Pose (Lite, model_complexity=1) at native video FPS.
          </li>
          <li>
            • Body height is normalised to 1.82m for stride length, vGRF, and speed estimates.
          </li>
          <li>
            • Ball release is detected via bowling-wrist peak vertical position; FFC via front-ankle
            velocity zero-crossing.
          </li>
          <li>
            • Release speed is derived from wrist tangential velocity × moment arm scaling.
          </li>
        </ul>
      </div>
    </AppShell>
  );
}
