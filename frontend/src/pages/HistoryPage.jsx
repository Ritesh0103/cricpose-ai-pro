import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import HistoryTable from "@/components/HistoryTable";
import { api } from "@/lib/api";

export default function HistoryPage() {
  const [reports, setReports] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.reports().then(setReports).catch((err) => setError(err.message));
  }, []);

  return (
    <AppShell
      eyebrow="Analysis history"
      title="Your saved sessions"
      description="Every upload is stored here so you can revisit old sessions and compare progress over time."
    >
      {error ? <div className="panel"><p className="text-[var(--danger)] text-sm">{error}</p></div> : null}
      <HistoryTable reports={reports} />
    </AppShell>
  );
}
