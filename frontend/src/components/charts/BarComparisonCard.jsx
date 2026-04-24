import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * Horizontal bar showing user value vs benchmark. Used for front knee FFC/BR, vGRF, ball speed.
 */
export default function BarComparisonCard({ title, subtitle, user, benchmark, unit = "°", userColor = "#57f0ff", benchmarkColor = "#f4c15d" }) {
  const data = [
    { name: "You", value: Number(user) || 0, fill: userColor },
    { name: "Elite", value: Number(benchmark) || 0, fill: benchmarkColor },
  ];
  return (
    <div className="panel" data-testid={`bar-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="mb-3">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="muted text-sm">{subtitle}</p>
      </div>
      <div style={{ height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 12, right: 36 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis type="number" stroke="#91aeca" fontSize={11} />
            <YAxis type="category" dataKey="name" stroke="#91aeca" fontSize={12} width={60} />
            <Tooltip
              contentStyle={{
                background: "#091522",
                border: "1px solid rgba(122, 164, 200, 0.22)",
                borderRadius: 12,
              }}
              formatter={(v) => `${Number(v).toFixed(1)}${unit}`}
            />
            <Bar dataKey="value" radius={[0, 10, 10, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
              <LabelList dataKey="value" position="right" formatter={(v) => `${Number(v).toFixed(1)}${unit}`} fill="#eef8ff" fontSize={12} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
