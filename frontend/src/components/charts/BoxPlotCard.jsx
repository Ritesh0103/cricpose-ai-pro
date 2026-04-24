import { ResponsiveContainer } from "recharts";

const PALETTE = {
  accent: "#57f0ff",
  accent2: "#86ff9f",
  warning: "#ffbd59",
  danger: "#ff7575",
};

/**
 * SVG-based box plot (min / q1 / median / q3 / max) with benchmark marker.
 * Renders inline so it stays simple and responsive without extra deps.
 */
export default function BoxPlotCard({
  title,
  subtitle,
  stats,
  benchmark,
  unit = "°",
  color = PALETTE.accent,
}) {
  if (!stats) return null;
  const { min, q1, median, q3, max, mean } = stats;
  const lo = Math.min(min, benchmark?.min ?? min);
  const hi = Math.max(max, benchmark?.max ?? max);
  const span = Math.max(hi - lo, 0.01);
  const pct = (v) => ((v - lo) / span) * 100;
  return (
    <div className="panel" data-testid={`boxplot-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="mb-3">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="muted text-sm">{subtitle}</p>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        {(() => {
          return (
            <svg viewBox="0 0 400 120" width="100%" height="120" preserveAspectRatio="none">
              <defs>
                <linearGradient id={`boxGrad-${title}`} x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor={color} stopOpacity="0.6" />
                  <stop offset="100%" stopColor={color} stopOpacity="0.15" />
                </linearGradient>
              </defs>
              {/* scale */}
              {[0, 25, 50, 75, 100].map((p) => (
                <line
                  key={p}
                  x1={(p / 100) * 400}
                  x2={(p / 100) * 400}
                  y1="0"
                  y2="120"
                  stroke="rgba(255,255,255,0.06)"
                />
              ))}
              {/* whiskers */}
              <line
                x1={(pct(min) / 100) * 400}
                x2={(pct(max) / 100) * 400}
                y1="60"
                y2="60"
                stroke={color}
                strokeWidth="1.5"
                strokeDasharray="4 4"
                opacity="0.6"
              />
              {/* box */}
              <rect
                x={(pct(q1) / 100) * 400}
                y="36"
                width={Math.max(((pct(q3) - pct(q1)) / 100) * 400, 2)}
                height="48"
                rx="6"
                fill={`url(#boxGrad-${title})`}
                stroke={color}
                strokeWidth="1.5"
              />
              {/* median */}
              <line
                x1={(pct(median) / 100) * 400}
                x2={(pct(median) / 100) * 400}
                y1="30"
                y2="90"
                stroke="#f8fbff"
                strokeWidth="2"
              />
              {/* mean dot */}
              <circle
                cx={(pct(mean) / 100) * 400}
                cy="60"
                r="4"
                fill={color}
                stroke="#02121e"
                strokeWidth="1.5"
              />
              {/* benchmark tick */}
              {benchmark?.ideal !== undefined ? (
                <line
                  x1={(pct(benchmark.ideal) / 100) * 400}
                  x2={(pct(benchmark.ideal) / 100) * 400}
                  y1="16"
                  y2="104"
                  stroke={PALETTE.warning}
                  strokeWidth="2"
                />
              ) : null}
            </svg>
          );
        })()}
      </ResponsiveContainer>
      <div className="grid grid-cols-4 gap-2 mt-3 text-xs muted">
        <div>
          <div className="uppercase tracking-wider">Min</div>
          <div className="text-[var(--text)] font-semibold">
            {min.toFixed(1)}
            {unit}
          </div>
        </div>
        <div>
          <div className="uppercase tracking-wider">Median</div>
          <div className="text-[var(--text)] font-semibold">
            {median.toFixed(1)}
            {unit}
          </div>
        </div>
        <div>
          <div className="uppercase tracking-wider">Mean</div>
          <div className="text-[var(--text)] font-semibold">
            {mean.toFixed(1)}
            {unit}
          </div>
        </div>
        <div>
          <div className="uppercase tracking-wider">Max</div>
          <div className="text-[var(--text)] font-semibold">
            {max.toFixed(1)}
            {unit}
          </div>
        </div>
      </div>
      {benchmark?.ideal !== undefined ? (
        <div className="text-xs muted mt-2">
          <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: PALETTE.warning }} />
          Elite benchmark ≈ {benchmark.ideal}
          {unit}
        </div>
      ) : null}
    </div>
  );
}
