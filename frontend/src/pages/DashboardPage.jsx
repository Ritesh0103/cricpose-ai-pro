import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Gauge, ShieldAlert, Sparkles, TrendingUp } from "lucide-react";
import AppShell from "@/components/AppShell";
import HistoryTable from "@/components/HistoryTable";
import ProgressChart from "@/components/charts/ProgressChart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [reports, setReports] = useState([]);

  useEffect(() => {
    Promise.all([api.dashboard(), api.reports()])
      .then(([dash, list]) => {
        setSummary(dash);
        setReports(list);
      })
      .catch(() => {});
  }, []);

  const latest = summary?.latest || null;
  const trend = summary?.score_trend || [];

  // Weekly improvement: delta between last point and earliest point in trend window
  let weeklyDelta = 0;
  if (trend.length >= 2) {
    weeklyDelta = trend[trend.length - 1].overall_score - trend[0].overall_score;
  }

  const cards = [
    {
      label: "Total sessions",
      value: summary?.total_reports ?? 0,
      testid: "stat-total-sessions",
      icon: Sparkles,
      accent: "#57f0ff",
    },
    {
      label: "Average score",
      value: (summary?.average_overall_score ?? 0).toFixed(1),
      testid: "stat-average-score",
      icon: Gauge,
      accent: "#86ff9f",
    },
    {
      label: "Best score",
      value: (summary?.best_score ?? 0).toFixed(1),
      testid: "stat-best-score",
      icon: TrendingUp,
      accent: "#ffbd59",
    },
    {
      label: "Injury band",
      value: latest?.injury_band || "—",
      testid: "stat-injury-band",
      icon: ShieldAlert,
      accent:
        latest?.injury_band === "High"
          ? "#ff7575"
          : latest?.injury_band === "Moderate"
            ? "#ffbd59"
            : "#86ff9f",
    },
  ];

  return (
    <AppShell
      eyebrow="Coaching dashboard"
      title={`Welcome back, ${user?.full_name?.split(" ")?.[0] || "Athlete"}`}
      description="Your saved sessions, biomechanics progression, and latest bowling analysis highlights."
    >
      <div className="grid gap-4 md:grid-cols-4" data-testid="dashboard-stats">
        {cards.map((c) => (
          <div
            className="stat-card flex items-start gap-3"
            key={c.label}
            data-testid={c.testid}
          >
            <div
              className="w-10 h-10 rounded-xl grid place-items-center"
              style={{
                background: `linear-gradient(135deg, ${c.accent}22, ${c.accent}05)`,
                border: `1px solid ${c.accent}33`,
              }}
            >
              <c.icon className="w-5 h-5" style={{ color: c.accent }} />
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.18em] muted">{c.label}</div>
              <div className="text-2xl font-semibold mt-1">{c.value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-[1.3fr_0.7fr]">
        <ProgressChart data={trend} />

        <div className="panel flex flex-col gap-3" data-testid="latest-session-card">
          <div className="flex justify-between items-start">
            <div>
              <div className="eyebrow">Latest session</div>
              <h3 className="text-lg font-semibold mt-1">
                {latest?.title || "No sessions yet"}
              </h3>
            </div>
            {latest ? (
              <Badge
                className={`text-xs ${
                  latest.injury_band === "High"
                    ? "bg-[rgba(255,117,117,0.18)] text-[#ff9a9a] border-transparent"
                    : latest.injury_band === "Moderate"
                      ? "bg-[rgba(255,189,89,0.18)] text-[#ffbd59] border-transparent"
                      : "bg-[rgba(134,255,159,0.18)] text-[#8cffb2] border-transparent"
                }`}
              >
                {latest.injury_band || "Low"} risk
              </Badge>
            ) : null}
          </div>
          {latest ? (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div className="stat-card" data-testid="latest-action">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Action</div>
                  <div className="font-semibold mt-1">{latest.action_label}</div>
                </div>
                <div className="stat-card" data-testid="latest-speed">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Release speed</div>
                  <div className="font-semibold mt-1">
                    {Number(latest.release_speed_kph || 0).toFixed(1)} kph
                  </div>
                </div>
                <div className="stat-card" data-testid="latest-score">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Overall</div>
                  <div className="font-semibold mt-1">
                    {Number(latest.overall_score || 0).toFixed(1)}
                  </div>
                </div>
                <div className="stat-card" data-testid="latest-injury">
                  <div className="text-xs uppercase tracking-[0.18em] muted">Injury prob.</div>
                  <div className="font-semibold mt-1">
                    {Number(latest.injury_probability || 0).toFixed(0)}%
                  </div>
                </div>
              </div>
              <div className="flex gap-2 mt-1">
                <Link to={`/analysis?report=${latest.id}`} className="flex-1">
                  <Button className="btn-brand w-full" data-testid="latest-open-btn">
                    Open report <ArrowUpRight className="w-4 h-4 ml-1" />
                  </Button>
                </Link>
                <Link to="/compare">
                  <Button variant="outline" className="btn-outline-brand" data-testid="latest-compare-btn">
                    Compare
                  </Button>
                </Link>
              </div>
            </>
          ) : (
            <div className="stat-card">
              <p className="muted text-sm">
                Upload your first delivery from the Analysis page to unlock session insights.
              </p>
              <Link to="/analysis">
                <Button className="btn-brand mt-3" data-testid="upload-first-btn">
                  Start first analysis
                </Button>
              </Link>
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_1.3fr]">
        <div className="panel flex flex-col gap-3" data-testid="weekly-summary-card">
          <div className="eyebrow">Performance trend</div>
          <h3 className="text-lg font-semibold">
            {weeklyDelta >= 0 ? "You're trending up" : "Trending down this window"}
          </h3>
          <div className="flex items-baseline gap-2">
            <div
              className="text-3xl font-semibold"
              style={{ color: weeklyDelta >= 0 ? "#86ff9f" : "#ff7575" }}
            >
              {weeklyDelta >= 0 ? "+" : ""}
              {weeklyDelta.toFixed(1)}
            </div>
            <div className="muted text-sm">pts over last {trend.length || 0} sessions</div>
          </div>
          <div className="h-2 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
            <span
              className="block h-full transition-all duration-700"
              style={{
                width: `${Math.min(Math.abs(weeklyDelta) * 4, 100)}%`,
                background:
                  weeklyDelta >= 0
                    ? "linear-gradient(135deg, #57f0ff, #86ff9f)"
                    : "linear-gradient(135deg, #ff7575, #ffbd59)",
              }}
            />
          </div>
          <p className="muted text-sm">
            {weeklyDelta >= 3
              ? "Strong progression — keep the current rhythm routine."
              : weeklyDelta > 0
                ? "Gradual improvement. Focus on front-leg brace for the next +5 pts."
                : trend.length < 2
                  ? "Upload more sessions to unlock progress tracking."
                  : "Slight regression. Review your latest session's coaching tips."}
          </p>
        </div>

        <div className="panel flex flex-col gap-3" data-testid="compare-cta-card">
          <div className="eyebrow">Benchmark with the pros</div>
          <h3 className="text-lg font-semibold">
            Compare your action with Bumrah, Starc, Steyn, Cummins & more
          </h3>
          <p className="muted text-sm">
            Weighted 12-metric similarity scoring against elite fast bowlers. Discover which legend
            your action most resembles and where the biggest biomechanical gaps sit.
          </p>
          <div className="flex flex-wrap gap-2">
            {["Bumrah", "Starc", "Steyn", "Cummins", "Anderson", "Brett Lee", "Shami"].map(
              (name) => (
                <span
                  key={name}
                  className="text-xs px-3 py-1 rounded-full border border-[var(--line)] muted"
                >
                  {name}
                </span>
              ),
            )}
          </div>
          <Link to="/compare" className="mt-1">
            <Button className="btn-brand" data-testid="compare-cta-btn">
              Open compare <ArrowUpRight className="w-4 h-4 ml-1" />
            </Button>
          </Link>
        </div>
      </div>

      <HistoryTable reports={reports} />
    </AppShell>
  );
}
