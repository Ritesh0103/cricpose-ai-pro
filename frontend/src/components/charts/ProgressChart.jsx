import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * Session progress chart — overall score + release speed across the athlete's timeline.
 * Also used for release consistency (release speed over sessions).
 */
export default function ProgressChart({ data = [], variant = "score", title, subtitle }) {
  if (variant === "consistency") {
    return (
      <div className="panel" data-testid="chart-release-consistency">
        <div className="mb-3">
          <h3 className="text-base font-semibold">{title || "Release consistency"}</h3>
          <p className="muted text-sm">
            {subtitle || "Ball release speed across your saved sessions — lower variance = more consistent."}
          </p>
        </div>
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
              <XAxis dataKey="date" stroke="#91aeca" fontSize={11} />
              <YAxis stroke="#91aeca" fontSize={11} domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{
                  background: "#091522",
                  border: "1px solid rgba(122, 164, 200, 0.22)",
                  borderRadius: 12,
                }}
                formatter={(v) => `${Number(v).toFixed(1)} kph`}
              />
              <Line
                type="monotone"
                dataKey="release_speed_kph"
                stroke="#57f0ff"
                strokeWidth={2.4}
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  return (
    <div className="panel" data-testid="chart-progress">
      <div className="mb-3">
        <h3 className="text-base font-semibold">{title || "Session progress"}</h3>
        <p className="muted text-sm">
          {subtitle || "Overall, efficiency and injury-probability scores across your saved sessions."}
        </p>
      </div>
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="overallArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#57f0ff" stopOpacity="0.45" />
                <stop offset="100%" stopColor="#57f0ff" stopOpacity="0.02" />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis dataKey="date" stroke="#91aeca" fontSize={11} />
            <YAxis stroke="#91aeca" fontSize={11} domain={[0, 100]} />
            <Tooltip
              contentStyle={{
                background: "#091522",
                border: "1px solid rgba(122, 164, 200, 0.22)",
                borderRadius: 12,
              }}
            />
            <Legend wrapperStyle={{ color: "#d9ecff", fontSize: 12 }} />
            <Area
              type="monotone"
              dataKey="overall_score"
              stroke="#57f0ff"
              fill="url(#overallArea)"
              strokeWidth={2.4}
              name="Overall"
            />
            <Line
              type="monotone"
              dataKey="efficiency_score"
              stroke="#86ff9f"
              strokeWidth={2}
              dot={false}
              name="Efficiency"
            />
            <Line
              type="monotone"
              dataKey="injury_probability"
              stroke="#ff7575"
              strokeWidth={2}
              dot={false}
              name="Injury %"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
