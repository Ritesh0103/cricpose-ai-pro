import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <main className="page-shell">
        <div className="panel mt-16">
          <p className="muted">Checking your session…</p>
        </div>
      </main>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
