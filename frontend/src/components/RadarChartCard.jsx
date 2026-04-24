import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";

export default function RadarChartCard({ metrics = [] }) {
  const data = metrics.map((m) => ({
    subject: m.label,
    user: m.unit === "m" ? Number((m.athlete_value * 50).toFixed(1)) : m.athlete_value,
    benchmark: m.unit === "m" ? Number((m.benchmark_value * 50).toFixed(1)) : m.benchmark_value,
  }));
  return (
    <div className="panel" data-testid="radar-chart">
      <div className="mb-3">
        <h3 className="text-base font-semibold">Biomechanics radar</h3>
        <p className="muted text-sm">Weighted shape comparison against the selected pro benchmark.</p>
      </div>
      <div style={{ height: 340 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data}>
            <PolarGrid stroke="rgba(255,255,255,0.12)" />
            <PolarAngleAxis dataKey="subject" tick={{ fill: "#d9ecff", fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: "#091522",
                border: "1px solid rgba(122, 164, 200, 0.22)",
                borderRadius: 12,
              }}
            />
            <Legend wrapperStyle={{ color: "#d9ecff" }} />
            <Radar name="You" dataKey="user" stroke="#57f0ff" fill="#57f0ff" fillOpacity={0.3} strokeWidth={2} />
            <Radar
              name="Pro"
              dataKey="benchmark"
              stroke="#f4c15d"
              fill="#f4c15d"
              fillOpacity={0.18}
              strokeWidth={2}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
