import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import UploadCard from "@/components/UploadCard";
import AnalysisDashboard from "@/components/AnalysisDashboard";
import { api } from "@/lib/api";

export default function AnalysisPage() {
  const [searchParams] = useSearchParams();
  const reportId = searchParams.get("report");
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!reportId) return;
    api
      .report(reportId)
      .then((r) => {
        setReport(r);
        setError(null);
      })
      .catch((err) => setError(err.message));
  }, [reportId]);

  return (
    <AppShell
      eyebrow="Bowling video analyzer"
      title="Upload a delivery, unlock the biomechanics"
      description="Drop your clip for MediaPipe pose detection, automatic event tagging (FFC, release), and a research-grade biomechanics dashboard."
    >
      <UploadCard onComplete={setReport} />
      {error ? (
        <div className="panel" data-testid="analysis-error">
          <p className="text-[var(--danger)] text-sm">{error}</p>
        </div>
      ) : null}
      {report ? <AnalysisDashboard report={report} /> : null}
    </AppShell>
  );
}
