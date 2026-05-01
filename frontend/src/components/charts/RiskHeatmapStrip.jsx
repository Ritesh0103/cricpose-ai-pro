/**
 * Risk heatmap strip — one thin colored cell per frame.
 * Band "low"=cyan, "moderate"=amber, "high"=red.
 */
const BAND_COLORS = {
  low: "#57f0ff",
  moderate: "#ffbd59",
  high: "#ff7575",
};

export default function RiskHeatmapStrip({ data = [], title = "Frame-level lumbar-stress risk", subtitle }) {
  const total = data.length;
  return (
    <div className="panel" data-testid="risk-heatmap">
      <div className="mb-3">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="muted text-sm">
          {subtitle || "Trunk lateral flexion per frame — red means >30° (elevated lumbar load)."}
        </p>
      </div>
      <div className="flex gap-[2px] rounded-xl overflow-hidden bg-[rgba(255,255,255,0.04)] p-[2px] h-12">
        {data.map((cell, i) => (
          <div
            key={i}
            title={`Frame ${cell.frame} · ${cell.trunk_flex.toFixed(1)}°`}
            className="flex-1 transition-transform hover:scale-y-110"
            style={{
              background: BAND_COLORS[cell.band] || BAND_COLORS.low,
              opacity: cell.band === "high" ? 1 : cell.band === "moderate" ? 0.85 : 0.45,
            }}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs muted mt-2">
        <span>Frame 0</span>
        <span>{total} frames</span>
      </div>
      <div className="flex gap-3 text-xs muted mt-2">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: BAND_COLORS.low }} />
          &lt; 22°
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: BAND_COLORS.moderate }} />
          22–30°
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: BAND_COLORS.high }} />
          &gt; 30° (elevated)
        </span>
      </div>
    </div>
  );
}
