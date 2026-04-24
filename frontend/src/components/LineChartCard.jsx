import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function LineChartCard({ title, subtitle, data = [], color = "#57f0ff" }) {
  return (
    <div className="panel" data-testid={`line-chart-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="mb-3">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="muted text-sm">{subtitle || "Frame-by-frame movement trace"}</p>
      </div>
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="rgba(255,255,255,0.08)" strokeDasharray="3 3" />
            <XAxis dataKey="frame" stroke="#91aeca" fontSize={11} />
            <YAxis stroke="#91aeca" fontSize={11} />
            <Tooltip
              contentStyle={{
                background: "#091522",
                border: "1px solid rgba(122, 164, 200, 0.22)",
                borderRadius: 12,
              }}
            />
            <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2.4} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
