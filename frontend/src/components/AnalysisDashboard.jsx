import { useEffect, useRef, useState } from "react";
import { Download, FileText, Info, Sigma } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import ScoreRing from "@/components/ScoreRing";
import LineChartCard from "@/components/LineChartCard";
import ComparisonBars from "@/components/ComparisonBars";
import BarComparisonCard from "@/components/charts/BarComparisonCard";
import BoxPlotCard from "@/components/charts/BoxPlotCard";
import JointTrajectoryChart from "@/components/charts/JointTrajectoryChart";
import RiskHeatmapStrip from "@/components/charts/RiskHeatmapStrip";
import SymmetryChart from "@/components/charts/SymmetryChart";
import { api } from "@/lib/api";

function metricsToCompareRows(metrics = []) {
  return metrics.map((m) => ({
    key: m.metric.toLowerCase().replace(/\s+/g, "_"),
    label: m.metric,
    unit: m.unit,
    athlete_value: m.athlete,
    benchmark_value: m.benchmark,
    delta: m.delta,
    delta_percent: m.benchmark ? (m.delta / m.benchmark) * 100 : 0,
    weight: 0.25,
    similarity: Math.max(0, 100 - Math.abs(m.delta) * 2),
    status:
      m.athlete >= m.benchmark ? "better" : Math.abs(m.delta) < 6 ? "elite-benchmark" : "needs-work",
    insight:
      m.athlete >= m.benchmark
        ? `${m.metric} matches or beats the elite benchmark (${m.benchmark} ${m.unit}).`
        : `${m.metric} trails benchmark (${m.benchmark} ${m.unit}).`,
  }));
}

export default function AnalysisDashboard({ report }) {
  const videoRef = useRef(null);
  const [videoSources, setVideoSources] = useState({});
  const [thumbSrc, setThumbSrc] = useState(null);
  const [mediaError, setMediaError] = useState(null);
  const [activeTab, setActiveTab] = useState("compare");

  useEffect(() => {
    let active = true;
    const urls = [];
    const endpoints = {
      original: report.source_video_url,
      skeleton: report.processed_video_url,
      tracking: report.tracking_video_url,
      sidebyside: report.sidebyside_video_url,
      slowmo: report.slowmo_video_url,
    };
    async function load() {
      setMediaError(null);
      const next = {};
      try {
        for (const [key, url] of Object.entries(endpoints)) {
          if (!url) continue;
          const u = await api.protectedBlobUrl(url);
          if (!active) return;
          next[key] = u;
          urls.push(u);
        }
        if (report.thumbnail_url) {
          const t = await api.protectedBlobUrl(report.thumbnail_url);
          if (active) {
            setThumbSrc(t);
            urls.push(t);
          }
        }
        if (active) setVideoSources(next);
      } catch (err) {
        if (active) setMediaError(err.message);
      }
    }
    load();
    return () => {
      active = false;
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [
    report.processed_video_url,
    report.source_video_url,
    report.tracking_video_url,
    report.sidebyside_video_url,
    report.slowmo_video_url,
    report.thumbnail_url,
  ]);

  const motion = report.metrics?.motion_series || {};
  const joint = report.metrics?.joint_metrics || {};
  const scores = report.metrics?.scores || {};
  const summary = report.metrics?.summary || {};
  const classification = report.metrics?.classification || null;
  const injury = report.metrics?.injury_analysis || null;
  const distributions = report.metrics?.distribution_stats || {};
  const rows = metricsToCompareRows(report.metrics?.comparison_metrics);
  const resolvedVideoUrl = videoSources[
    {
      compare: "sidebyside",
      skeleton: "skeleton",
      tracking: "tracking",
      slowmo: "slowmo",
      original: "original",
    }[activeTab]
  ];

  useEffect(() => {
    if (resolvedVideoUrl) {
      console.log("CricPose videoUrl", resolvedVideoUrl);
    }
  }, [resolvedVideoUrl]);

  return (
    <div className="flex flex-col gap-5" data-testid="analysis-dashboard">
      <div className="grid gap-4 md:grid-cols-4">
        <ScoreRing value={summary.overall_score ?? report.overall_score} label="Overall" />
        <ScoreRing value={summary.efficiency_score ?? report.efficiency_score} label="Efficiency" />
        <ScoreRing value={summary.balance_score ?? report.balance_score} label="Balance" />
        <ScoreRing value={summary.consistency_score ?? report.consistency_score} label="Consistency" />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel" data-testid="biomechanics-panel">
          <div className="flex justify-between gap-3 mb-4">
            <div>
              <h2 className="text-lg font-semibold">Research-grade biomechanics</h2>
              <p className="muted text-sm">
                Single-camera estimates derived from MediaPipe pose landmarks and frame-level
                kinematics.
              </p>
            </div>
            <Badge className="btn-outline-brand self-start">
              {report.metrics?.video_meta?.bowling_arm === "left" ? "Left-arm" : "Right-arm"} bowler
            </Badge>
          </div>
          {classification || injury ? (
            <div className="grid gap-3 sm:grid-cols-2 mb-4">
              {classification ? (
                <div
                  className="stat-card border-[rgba(87,240,255,0.3)]"
                  data-testid="action-classification"
                >
                  <div className="text-xs uppercase tracking-[0.18em] muted">
                    Bowling action
                  </div>
                  <div className="text-lg font-semibold mt-1 flex items-center gap-2">
                    {classification.action_label}
                    <Badge className="btn-outline-brand">
                      {classification.confidence.toFixed(0)}% confidence
                    </Badge>
                  </div>
                  <p className="muted text-xs mt-2">{classification.description}</p>
                  <div className="text-xs muted mt-2">
                    Shoulder @ BFC {classification.shoulder_at_bfc_deg}° · @ FFC{" "}
                    {classification.shoulder_at_ffc_deg}° · Δ {classification.shoulder_delta_deg}°
                  </div>
                </div>
              ) : null}
              {injury ? (
                <div className="stat-card" data-testid="injury-probability">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="text-xs uppercase tracking-[0.18em] muted">
                        Injury probability
                      </div>
                      <div className="text-lg font-semibold mt-1">
                        {injury.probability.toFixed(0)}%
                      </div>
                    </div>
                    <Badge
                      className={`text-xs ${
                        injury.band === "High"
                          ? "bg-[rgba(255,117,117,0.2)] text-[#ff9a9a] border-transparent"
                          : injury.band === "Moderate"
                          ? "bg-[rgba(255,189,89,0.18)] text-[#ffbd59] border-transparent"
                          : "bg-[rgba(134,255,159,0.18)] text-[#8cffb2] border-transparent"
                      }`}
                    >
                      {injury.band} risk
                    </Badge>
                  </div>
                  <div className="h-2 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden mt-3">
                    <span
                      className="block h-full"
                      style={{
                        width: `${Math.min(injury.probability, 100)}%`,
                        background:
                          injury.band === "High"
                            ? "linear-gradient(135deg, #ff7575, #ffbd59)"
                            : injury.band === "Moderate"
                            ? "linear-gradient(135deg, #ffbd59, #86ff9f)"
                            : "linear-gradient(135deg, #57f0ff, #86ff9f)",
                      }}
                    />
                  </div>
                  <ul className="mt-3 flex flex-col gap-1">
                    {(injury.contributors || []).slice(0, 3).map((c, i) => (
                      <li key={i} className="text-xs muted">
                        • {c.label} <span className="ml-1 opacity-70">+{c.weight}</span>
                      </li>
                    ))}
                    {!(injury.contributors || []).length ? (
                      <li className="text-xs muted">
                        No elevated risk markers detected in this delivery.
                      </li>
                    ) : null}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="grid gap-3 sm:grid-cols-2">
            {(() => {
              const fmt = (value, unit) => {
                if (value === undefined || value === null) return "—";
                if (typeof value === "number" && !Number.isFinite(value)) return "—";
                if (typeof value === "number" && value === 0 && unit !== "°") return "—";
                return `${value}${unit}`;
              };
              const tiles = [
                ["Release angle", fmt(joint.release_angle_deg, "°")],
                ["Release height", fmt(joint.release_height_m, " m")],
                [
                  "Release speed (est.)",
                  fmt(joint.release_speed_kph ?? summary.approx_speed_kph, " kph"),
                ],
                ["Wrist velocity", fmt(joint.wrist_velocity_mps, " m/s")],
                ["Run-up speed", fmt(joint.runup_speed_kph, " kph")],
                ["Stride length", fmt(joint.stride_length_m, " m")],
                ["Pelvis-shoulder sep.", fmt(joint.pelvis_shoulder_separation_deg, "°")],
                ["Hip rotation speed", fmt(joint.hip_rotation_speed_dps, "°/s")],
                ["Trunk lateral flexion", fmt(joint.trunk_lateral_flexion_deg, "°")],
                ["Front knee @ FFC", fmt(joint.front_knee_flexion_ffc_deg, "°")],
                ["Front knee @ release", fmt(joint.front_knee_flexion_br_deg, "°")],
                ["Landing balance", fmt(joint.landing_balance_score, "/100")],
                ["vGRF (peak)", fmt(joint.vGRF_body_weights, " BW")],
                ["Shoulder alignment", fmt(joint.shoulder_alignment_deg, "°")],
                ["L/R symmetry", fmt(joint.symmetry_score, "/100")],
              ];
              return tiles.map(([label, value]) => (
                <div
                  key={label}
                  className="stat-card"
                  data-testid={`metric-${label.toLowerCase().replace(/[^a-z]+/g, "-")}`}
                >
                  <div className="text-xs uppercase tracking-[0.18em] muted">{label}</div>
                  <div className="text-lg font-semibold mt-1">{value}</div>
                </div>
              ));
            })()}
          </div>
        </div>

        <div className="panel" data-testid="visual-panel">
          <div className="flex justify-between gap-3 mb-4">
            <div>
              <h2 className="text-lg font-semibold">Video output</h2>
              <p className="muted text-sm">
                Original capture, AI skeleton overlay, joint-trail tracking, side-by-side
                comparison, and a slow-motion release cut.
              </p>
            </div>
            {report.pdf_report_url ? (
              <div className="flex gap-2 flex-wrap" data-testid="export-buttons">
                <Button
                  className="btn-brand"
                  size="sm"
                  onClick={() => api.downloadFile(report.pdf_report_url, `${report.title}.pdf`)}
                  data-testid="download-pdf-btn"
                >
                  <Download className="w-4 h-4 mr-2" /> PDF report
                </Button>
                <Button
                  variant="outline"
                  className="btn-outline-brand"
                  size="sm"
                  onClick={() => api.downloadCSV(report.id, "metrics")}
                  data-testid="download-csv-metrics-btn"
                >
                  <FileText className="w-4 h-4 mr-2" /> Metrics CSV
                </Button>
                <Button
                  variant="outline"
                  className="btn-outline-brand"
                  size="sm"
                  onClick={() => api.downloadCSV(report.id, "motion")}
                  data-testid="download-csv-motion-btn"
                >
                  <Sigma className="w-4 h-4 mr-2" /> Motion CSV
                </Button>
                <Button
                  variant="outline"
                  className="btn-outline-brand"
                  size="sm"
                  onClick={() => api.downloadCSV(report.id, "events")}
                  data-testid="download-csv-events-btn"
                >
                  <FileText className="w-4 h-4 mr-2" /> Events CSV
                </Button>
              </div>
            ) : null}
          </div>
          <div
            className="flex flex-wrap gap-2 mb-3"
            role="tablist"
            aria-label="Video outputs"
            data-testid="video-tabs"
          >
            {[
              { id: "compare", label: "Side-by-side", key: "sidebyside" },
              { id: "skeleton", label: "Skeleton overlay", key: "skeleton" },
              { id: "tracking", label: "Joint trails", key: "tracking" },
              { id: "slowmo", label: "Release slow-mo", key: "slowmo" },
              { id: "original", label: "Original", key: "original" },
            ].map((tab) => {
              const src = videoSources[tab.key];
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  disabled={!src}
                  className={`px-3 py-1.5 rounded-full text-xs tracking-wide uppercase transition-colors border ${
                    activeTab === tab.id
                      ? "bg-[rgba(87,240,255,0.14)] border-[rgba(87,240,255,0.45)] text-white"
                      : "border-[var(--line)] muted hover:text-white"
                  } ${!src ? "opacity-40 cursor-not-allowed" : ""}`}
                  data-testid={`video-tab-${tab.id}`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
          <div
            className="video-frame"
            data-testid={`video-player-${activeTab}`}
            key={activeTab}
          >
            {(() => {
              const TAB_TO_KEY = {
                compare: "sidebyside",
                skeleton: "skeleton",
                tracking: "tracking",
                slowmo: "slowmo",
                original: "original",
              };
              const activeSrc = videoSources[TAB_TO_KEY[activeTab]];
              return activeSrc ? (
                <video
                  ref={videoRef}
                  controls
                  autoPlay={false}
                  muted={false}
                  poster={thumbSrc || undefined}
                  style={{ width: "100%", borderRadius: "12px", pointerEvents: "auto" }}
                >
                  <source src={activeSrc} type="video/mp4" />
                </video>
              ) : (
                <div className="stat-card text-center text-sm muted p-8">
                  {mediaError ? mediaError : "Preparing this output…"}
                </div>
              );
            })()}
          </div>
          <p className="muted text-xs mt-2">
            {activeTab === "compare"
              ? "Left: original capture. Right: AI skeleton overlay."
              : activeTab === "skeleton"
              ? "33 MediaPipe pose landmarks rendered on every frame."
              : activeTab === "tracking"
              ? "Fading trails follow the bowling-side shoulder, wrist, and ankle."
              : activeTab === "slowmo"
              ? "±1.2s around the detected ball-release frame, at one-third playback speed."
              : "Clean uploaded clip, no processing overlays."}
          </p>
          {mediaError ? (
            <p className="text-sm text-[var(--warning)] mt-3">
              <Info className="inline w-4 h-4 mr-1" />
              {mediaError}
            </p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <LineChartCard
          title="Bowling arm angle"
          subtitle="Arm path across the delivery (degrees vs vertical)"
          color="#57f0ff"
          data={(motion.bowling_arm_angle || []).map((p) => ({ frame: p.frame, value: p.value }))}
        />
        <LineChartCard
          title="Front knee flexion"
          subtitle="Knee interior angle over time (brace window around release)"
          color="#86ff9f"
          data={(motion.front_knee_bend || []).map((p) => ({ frame: p.frame, value: p.value }))}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <LineChartCard
          title="Trunk lateral flexion"
          subtitle="Sideways trunk tilt across delivery (degrees)"
          color="#ffbd59"
          data={(motion.trunk_lateral_flexion || []).map((p) => ({ frame: p.frame, value: p.value }))}
        />
        <LineChartCard
          title="Pelvis-shoulder separation"
          subtitle="Torso wind-up angle per frame (degrees)"
          color="#d7a7ff"
          data={(motion.pelvis_shoulder_separation || []).map((p) => ({
            frame: p.frame,
            value: p.value,
          }))}
        />
      </div>

      <ComparisonBars
        metrics={rows}
        title="Snapshot against elite benchmark"
        description="Quick comparison based on this delivery's release, brace, separation, and stride."
      />

      {/* ---- Advanced biomechanics analytics ---- */}
      <div className="panel" data-testid="compare-link-card">
        <div className="flex flex-wrap justify-between items-center gap-3">
          <div>
            <h3 className="font-semibold">Benchmark this delivery against the pros</h3>
            <p className="muted text-sm">
              Run a weighted 12-metric similarity scan against Bumrah, Starc, Steyn, Cummins and more.
            </p>
          </div>
          <Link to={`/compare?report=${report.id}`}>
            <Button className="btn-brand" data-testid="open-compare-btn">
              Open compare mode
            </Button>
          </Link>
        </div>
      </div>

      {(motion.risk_heatmap || []).length ? (
        <RiskHeatmapStrip data={motion.risk_heatmap || []} />
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <BarComparisonCard
          title="Front knee at FFC"
          subtitle="Knee flexion at front-foot contact vs elite benchmark (150°)"
          user={joint.front_knee_flexion_ffc_deg}
          benchmark={150}
          unit="°"
        />
        <BarComparisonCard
          title="Front knee at release"
          subtitle="Knee extension at ball release vs elite benchmark (170°)"
          user={joint.front_knee_flexion_br_deg}
          benchmark={170}
          unit="°"
        />
        <BarComparisonCard
          title="Peak vGRF"
          subtitle="Estimated vertical ground reaction force vs elite 5 BW reference"
          user={joint.vGRF_body_weights}
          benchmark={5}
          unit=" BW"
          userColor="#ffbd59"
        />
        <BarComparisonCard
          title="Ball release speed"
          subtitle="Wrist-speed derived release velocity vs 138 kph elite reference"
          user={joint.release_speed_kph}
          benchmark={138}
          unit=" kph"
          userColor="#86ff9f"
        />
      </div>

      {Object.keys(distributions).length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {distributions.shoulder_alignment ? (
            <BoxPlotCard
              title="Shoulder alignment"
              subtitle="Deviation from horizontal across the delivery (lower = more aligned)"
              stats={distributions.shoulder_alignment}
              benchmark={{ ideal: 9, min: 0, max: 25 }}
              unit="°"
              color="#57f0ff"
            />
          ) : null}
          {distributions.pelvis_shoulder_separation ? (
            <BoxPlotCard
              title="Pelvis-shoulder separation"
              subtitle="Torso wind-up spread across delivery (elite band ~35–45°)"
              stats={distributions.pelvis_shoulder_separation}
              benchmark={{ ideal: 42, min: 0, max: 90 }}
              unit="°"
              color="#86ff9f"
            />
          ) : null}
          {distributions.trunk_lateral_flexion ? (
            <BoxPlotCard
              title="Trunk lateral flexion"
              subtitle="Sideways trunk tilt (>30° raises lumbar-stress risk)"
              stats={distributions.trunk_lateral_flexion}
              benchmark={{ ideal: 22, min: 0, max: 45 }}
              unit="°"
              color="#ffbd59"
            />
          ) : null}
          {distributions.front_knee_bend ? (
            <BoxPlotCard
              title="Front knee bend distribution"
              subtitle="Interior knee angle distribution across the full delivery"
              stats={distributions.front_knee_bend}
              benchmark={{ ideal: 170, min: 120, max: 180 }}
              unit="°"
              color="#d7a7ff"
            />
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {(motion.symmetry || []).length ? <SymmetryChart data={motion.symmetry} /> : null}
        {(motion.wrist_trajectory || []).length ? (
          <JointTrajectoryChart data={motion.wrist_trajectory} />
        ) : null}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel" data-testid="good-points-panel">
          <h3 className="text-base font-semibold mb-2">What's working</h3>
          <ul className="flex flex-col gap-2">
            {(report.metrics?.good_points || []).map((g) => (
              <li key={g} className="stat-card">
                {g}
              </li>
            ))}
            {!(report.metrics?.good_points || []).length ? (
              <li className="muted text-sm">No strong positives detected yet.</li>
            ) : null}
          </ul>
        </div>
        <div className="panel" data-testid="errors-panel">
          <h3 className="text-base font-semibold mb-2">Errors & risks</h3>
          <ul className="flex flex-col gap-2">
            {(report.metrics?.errors_detected || []).map((e) => (
              <li key={e} className="stat-card">
                {e}
              </li>
            ))}
            {(report.metrics?.injury_risk || []).map((r) => (
              <li key={r.label} className="stat-card">
                <strong>{r.label}:</strong> {r.level}.{" "}
                <span className="muted">{r.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel" data-testid="coaching-panel">
          <h3 className="text-base font-semibold mb-2">Coaching tips</h3>
          <ul className="flex flex-col gap-2">
            {(report.metrics?.coaching_tips || []).map((t) => (
              <li key={t.title} className="stat-card">
                <strong>{t.title}</strong>
                <div className="muted text-sm mt-1">{t.detail}</div>
              </li>
            ))}
          </ul>
        </div>
        <div className="panel" data-testid="events-panel">
          <h3 className="text-base font-semibold mb-2">Delivery events</h3>
          <ul className="flex flex-col gap-2">
            {(report.metrics?.frame_events || []).map((e) => (
              <li key={`${e.label}-${e.frame}`} className="stat-card">
                <strong>{e.label}</strong>
                <div className="muted text-sm">
                  Frame {e.frame} · {Number(e.timestamp).toFixed(2)}s · Confidence{" "}
                  {Math.round(e.confidence * 100)}%
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
