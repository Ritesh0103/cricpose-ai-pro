import clsx from "clsx";
import { Badge } from "@/components/ui/badge";

function formatValue(value, unit) {
  if (unit === "m") return `${Number(value).toFixed(2)}m`;
  if (unit === "deg") return `${Number(value).toFixed(1)}°`;
  return Number(value).toFixed(1);
}

export default function ComparisonBars({
  metrics = [],
  title = "Metric-by-metric comparison",
  description = "Weighted biomechanics signals against the selected elite reference.",
}) {
  return (
    <div className="panel" data-testid="comparison-bars">
      <div className="mb-4">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="muted text-sm">{description}</p>
      </div>
      <div className="flex flex-col gap-4">
        {metrics.map((m) => {
          const maxValue = Math.max(m.athlete_value, m.benchmark_value, 0.1);
          const athleteWidth =
            m.unit === "m"
              ? Math.min((m.athlete_value / maxValue) * 100, 100)
              : Math.min(m.athlete_value, 100);
          const benchmarkWidth =
            m.unit === "m"
              ? Math.min((m.benchmark_value / maxValue) * 100, 100)
              : Math.min(m.benchmark_value, 100);
          return (
            <div
              key={m.key}
              className="rounded-xl border border-[var(--line)] bg-[rgba(255,255,255,0.02)] p-4"
            >
              <div className="flex justify-between gap-3 mb-3">
                <div>
                  <div className="font-medium">{m.label}</div>
                  <div className="muted text-sm">{m.insight}</div>
                </div>
                <Badge
                  className={clsx("shrink-0", {
                    "bg-[rgba(134,255,159,0.14)] text-[#8cffb2] border-transparent":
                      m.status === "better",
                    "bg-[rgba(255,117,117,0.14)] text-[#ff9a9a] border-transparent":
                      m.status === "needs-work",
                    "bg-[rgba(244,193,93,0.14)] text-[#f4c15d] border-transparent":
                      m.status === "elite-benchmark",
                  })}
                >
                  {m.status === "better"
                    ? "You lead"
                    : m.status === "needs-work"
                    ? "Needs work"
                    : "On benchmark"}
                </Badge>
              </div>
              <div className="flex flex-col gap-2">
                <div>
                  <div className="flex justify-between text-xs muted mb-1">
                    <span>You</span>
                    <strong>{formatValue(m.athlete_value, m.unit)}</strong>
                  </div>
                  <div className="h-2 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
                    <span
                      className="block h-full"
                      style={{
                        width: `${athleteWidth}%`,
                        background: "linear-gradient(135deg, #57f0ff, #86ff9f)",
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs muted mb-1">
                    <span>Benchmark</span>
                    <strong>{formatValue(m.benchmark_value, m.unit)}</strong>
                  </div>
                  <div className="h-2 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
                    <span
                      className="block h-full"
                      style={{
                        width: `${benchmarkWidth}%`,
                        background: "linear-gradient(135deg, #f4c15d, #ffc978)",
                      }}
                    />
                  </div>
                </div>
              </div>
              <div className="flex justify-between text-xs muted mt-3">
                <span>Similarity {m.similarity.toFixed(1)}%</span>
                <span>
                  Δ {m.delta > 0 ? "+" : ""}
                  {m.delta.toFixed(1)} {m.unit}
                </span>
                <span>Weight {(m.weight * 100).toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
