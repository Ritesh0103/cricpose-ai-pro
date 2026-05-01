import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const navigate = useNavigate();
  const { signup, guestLogin } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await signup(
        String(form.get("full_name")),
        String(form.get("email")),
        String(form.get("password")),
      );
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
    <main className="min-h-screen grid place-items-center p-6" data-testid="signup-page">
      <form className="panel w-full max-w-md" onSubmit={onSubmit} data-testid="signup-form">
        <div className="flex items-center gap-3 mb-4">
          <span className="brand-mark">CP</span>
          <div>
            <div className="eyebrow">Join CricPose</div>
            <div className="text-lg font-semibold">Create your athlete account</div>
          </div>
        </div>
        <p className="muted text-sm mb-5">
          Save bowling analyses, compare sessions, and build a history of technical progress.
        </p>
        <div className="flex flex-col gap-3">
          <div>
            <Label htmlFor="full_name">Full name</Label>
            <Input id="full_name" name="full_name" required data-testid="signup-name" />
          </div>
          <div>
            <Label htmlFor="email">Email</Label>
            <Input id="email" name="email" type="email" required data-testid="signup-email" />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              minLength={6}
              required
              data-testid="signup-password"
            />
          </div>
        </div>
        {error ? (
          <p className="text-[var(--danger)] text-sm mt-3" data-testid="signup-error">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-3 mt-5">
          <Button type="submit" className="btn-brand" disabled={submitting} data-testid="signup-submit">
            {submitting ? "Creating…" : "Create account"}
          </Button>
          <Link to="/login">
            <Button type="button" variant="outline" className="btn-outline-brand">
              Login
            </Button>
          </Link>
          <Button
            type="button"
            variant="outline"
            className="btn-outline-brand"
            onClick={onGuest}
            disabled={guestLoading}
            data-testid="guest-signup-btn"
          >
            {guestLoading ? "Entering…" : "Continue as guest"}
          </Button>
        </div>
      </form>
    </main>
  );
}
