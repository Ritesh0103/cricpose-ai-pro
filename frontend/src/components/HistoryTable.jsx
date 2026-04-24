import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export default function HistoryTable({ reports = [] }) {
  if (!reports.length) {
    return (
      <div className="panel" data-testid="history-empty">
        <p className="muted">
          No analysis reports yet. Upload your first bowling delivery from the Analysis page.
        </p>
      </div>
    );
  }
  return (
    <div className="panel" data-testid="history-table-panel">
      <div className="mb-4 flex justify-between items-start">
        <div>
          <h2 className="text-lg font-semibold">Saved Reports</h2>
          <p className="muted text-sm">Reopen past sessions, compare progress, re-run comparisons.</p>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse" data-testid="history-table">
          <thead>
            <tr className="text-left text-xs uppercase tracking-[0.18em] muted">
              <th className="py-3 border-b border-[var(--line)]">Session</th>
              <th className="py-3 border-b border-[var(--line)]">Date</th>
              <th className="py-3 border-b border-[var(--line)]">Overall</th>
              <th className="py-3 border-b border-[var(--line)]">Efficiency</th>
              <th className="py-3 border-b border-[var(--line)]" />
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id} data-testid={`history-row-${r.id}`}>
                <td className="py-3 border-b border-[var(--line)]">{r.title}</td>
                <td className="py-3 border-b border-[var(--line)] muted">
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td className="py-3 border-b border-[var(--line)] font-semibold">
                  {Number(r.overall_score).toFixed(1)}
                </td>
                <td className="py-3 border-b border-[var(--line)]">
                  {Number(r.efficiency_score).toFixed(1)}
                </td>
                <td className="py-3 border-b border-[var(--line)] text-right">
                  <Link to={`/analysis?report=${r.id}`} data-testid={`open-report-${r.id}`}>
                    <Button variant="outline" size="sm" className="btn-outline-brand">
                      Open
                    </Button>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
