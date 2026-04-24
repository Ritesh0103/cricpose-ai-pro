import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell from "@/components/AppShell";
import RadarChartCard from "@/components/RadarChartCard";
import ComparisonBars from "@/components/ComparisonBars";
import ScoreRing from "@/components/ScoreRing";
import MultiProRadar from "@/components/charts/MultiProRadar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";

const FILTERS = [
  { value: "closest", label: "Closest match" },
  { value: "pace_legends", label: "Pace legends" },
  { value: "swing_bowlers", label: "Swing bowlers" },
  { value: "sling_actions", label: "Sling actions" },
  { value: "custom", label: "Custom bowler" },
];

export default function ComparePage() {
  const [searchParams] = useSearchParams();
  const preselectReport = searchParams.get("report");
  const [reports, setReports] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [analysisId, setAnalysisId] = useState("");
  const [mode, setMode] = useState("closest");
  const [bowler, setBowler] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [overlayNames, setOverlayNames] = useState([]);
  const [athleteReport, setAthleteReport] = useState(null);

  useEffect(() => {
    Promise.all([api.reports(), api.compareProfiles()])
      .then(([r, p]) => {
        setReports(r);
        setProfiles(p);
        const target = preselectReport && r.find((x) => x.id === preselectReport);
        if (target) setAnalysisId(target.id);
        else if (r[0]) setAnalysisId(r[0].id);
        if (p[0]) {
          setBowler(p[0].name);
          setOverlayNames(p.slice(0, 3).map((x) => x.name));
        }
      })
      .catch((err) => setError(err.message));
  }, [preselectReport]);

  useEffect(() => {
    if (!analysisId) return;
    if (mode === "custom" && !bowler) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.compare({
        analysis_id: analysisId,
        target_bowler: mode === "custom" ? bowler : null,
        comparison_group: mode,
      }),
      api.report(analysisId),
    ])
      .then(([compare, rep]) => {
        setData(compare);
        setAthleteReport(rep);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [analysisId, mode, bowler]);

  const headline = useMemo(() => {
    if (!data) return "Select a saved analysis to find your closest elite action match.";
    return `Your action is ${data.similarity_score.toFixed(1)}% aligned with ${data.best_match.name}.`;
  }, [data]);

  return (
    <AppShell
      eyebrow="Elite biomechanics benchmarking"
      title="Compare with the pros"
      description={headline}
    >
      <div className="panel" data-testid="compare-filters">
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <div className="text-xs uppercase tracking-[0.18em] muted mb-2">Select analysis</div>
            <Select
              value={analysisId}
              onValueChange={setAnalysisId}
              disabled={!reports.length}
            >
              <SelectTrigger data-testid="compare-analysis-select">
                <SelectValue placeholder={reports.length ? "Pick a session" : "No analyses yet"} />
              </SelectTrigger>
              <SelectContent>
                {reports.map((r) => (
                  <SelectItem key={r.id} value={r.id} data-testid={`compare-option-${r.id}`}>
                    {r.title} — {Number(r.overall_score).toFixed(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] muted mb-2">Filter</div>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger data-testid="compare-mode-select">
                <SelectValue placeholder="Choose mode" />
              </SelectTrigger>
              <SelectContent>
                {FILTERS.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {mode === "custom" ? (
            <div>
              <div className="text-xs uppercase tracking-[0.18em] muted mb-2">Bowler</div>
              <Select value={bowler} onValueChange={setBowler}>
                <SelectTrigger data-testid="compare-bowler-select">
                  <SelectValue placeholder="Pick bowler" />
                </SelectTrigger>
                <SelectContent>
                  {profiles.map((p) => (
                    <SelectItem key={p.name} value={p.name}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="panel">
          <p className="text-[var(--danger)] text-sm">{error}</p>
        </div>
      ) : null}

      {loading ? (
        <div className="panel">
          <p className="muted text-sm">Running elite benchmark comparison…</p>
        </div>
      ) : null}

      <div className="panel" data-testid="multi-pro-overlay-panel">
        <div className="flex flex-wrap justify-between gap-3 items-start mb-4">
          <div>
            <h3 className="font-semibold">Overlay multiple pros</h3>
            <p className="muted text-sm">
              Click a bowler to toggle overlay — shape how your action stacks against multiple
              legends on a single radar.
            </p>
          </div>
          <div className="flex flex-wrap gap-2" data-testid="pro-overlay-chips">
            {profiles.map((p) => {
              const active = overlayNames.includes(p.name);
              return (
                <Button
                  key={p.name}
                  type="button"
                  size="sm"
                  variant={active ? "default" : "outline"}
                  className={active ? "btn-brand" : "btn-outline-brand"}
                  onClick={() =>
                    setOverlayNames((names) =>
                      active ? names.filter((n) => n !== p.name) : [...names, p.name],
                    )
                  }
                  data-testid={`overlay-chip-${p.name.toLowerCase().replace(/\s+/g, "-")}`}
                >
                  {p.name}
                </Button>
              );
            })}
          </div>
        </div>
        <MultiProRadar
          athleteMetrics={athleteReport?.metrics?.comparison_inputs || {}}
          pros={profiles.filter((p) => overlayNames.includes(p.name))}
        />
      </div>

      {data ? (
        <>
          <div className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
            <div className="panel" data-testid="best-match-panel">
              <div className="flex items-center gap-4">
                <div
                  className="w-16 h-16 rounded-2xl grid place-items-center text-xl font-bold text-[#032033]"
                  style={{
                    background: `linear-gradient(135deg, ${data.best_match.visual.primary}, ${data.best_match.visual.secondary})`,
                  }}
                >
                  {data.best_match.visual.label}
                </div>
                <div>
                  <h2 className="text-xl font-semibold">{data.best_match.name}</h2>
                  <Badge className="mt-1 btn-outline-brand">{data.best_match.style}</Badge>
                </div>
              </div>
              <div className="grid gap-3 grid-cols-2 mt-4">
                <div className="stat-card">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Handedness</div>
                  <div className="font-semibold mt-1">{data.best_match.handedness}</div>
                </div>
                <div className="stat-card">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Speed range</div>
                  <div className="font-semibold mt-1">
                    {data.best_match.speed_range[0]}–{data.best_match.speed_range[1]} kph
                  </div>
                </div>
              </div>
              <p className="muted text-sm mt-4">{data.best_match.archetype}</p>
            </div>
            <div className="panel" data-testid="similarity-panel">
              <ScoreRing value={data.similarity_score} label="Similarity %" />
              <p className="muted text-sm mt-3">
                Weighted across twelve biomechanics signals: release, brace, separation, arm speed,
                alignment, stride, balance, consistency.
              </p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <RadarChartCard metrics={data.compared_metrics} />
            <div className="panel" data-testid="insights-panel">
              <h3 className="font-semibold mb-2">Smart insights</h3>
              <div className="flex flex-col gap-3">
                <div className="stat-card">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Best edge</div>
                  <div className="mt-1">
                    {data.strengths[0] || "Run a comparison to reveal your strongest match point."}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Primary gap</div>
                  <div className="mt-1">
                    {data.weaknesses[0] || "The system will flag the biggest biomechanical gap here."}
                  </div>
                </div>
                <ul className="flex flex-col gap-2">
                  {data.coaching_tips.map((tip) => (
                    <li key={tip} className="stat-card">
                      {tip}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          <ComparisonBars
            metrics={data.compared_metrics}
            title="Metric-by-metric comparison"
            description="Hover to inspect deltas, weights and similarity scores per metric."
          />
        </>
      ) : null}
    </AppShell>
  );
}
