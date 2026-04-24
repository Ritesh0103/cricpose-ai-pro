import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, guestLogin } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await login(String(form.get("email")), String(form.get("password")));
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const onGuest = async () => {
    setGuestLoading(true);
    setError(null);
    try {
      await guestLogin();
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    } finally {
      setGuestLoading(false);
    }
  };

  return (
    <main className="min-h-screen grid place-items-center p-6" data-testid="login-page">
      <form className="panel w-full max-w-md" onSubmit={onSubmit} data-testid="login-form">
        <div className="flex items-center gap-3 mb-4">
          <span className="brand-mark">CP</span>
          <div>
            <div className="eyebrow">Login</div>
            <div className="text-lg font-semibold">CricPose AI Pro</div>
          </div>
        </div>
        <p className="muted text-sm mb-5">
          Access your saved reports, upload new videos, and track bowling progression.
        </p>
        <div className="flex flex-col gap-3">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" name="email" type="email" required data-testid="login-email" />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input id="password" name="password" type="password" required data-testid="login-password" />
          </div>
        </div>
        {error ? (
          <p className="text-[var(--danger)] text-sm mt-3" data-testid="login-error">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3 mt-5">
          <Button type="submit" className="btn-brand" disabled={submitting} data-testid="login-submit">
            {submitting ? "Signing in…" : "Login"}
          </Button>
          <Link to="/signup">
            <Button type="button" variant="outline" className="btn-outline-brand">
              Create account
            </Button>
          </Link>
          <Button
            type="button"
            variant="outline"
            className="btn-outline-brand"
            onClick={onGuest}
            disabled={guestLoading}
            data-testid="guest-login-btn"
          >
            {guestLoading ? "Entering…" : "Continue as guest"}
          </Button>
        </div>
      </form>
    </main>
  );
}
