import {
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
 * Symmetry chart — overlays left vs right knee extension per frame.
 * Visual gap highlights kinematic asymmetry (injury-risk signal).
 */
export default function SymmetryChart({ data = [] }) {
  return (
    <div className="panel" data-testid="chart-symmetry">
      <div className="mb-3">
        <h3 className="text-base font-semibold">Left vs right knee extension</h3>
        <p className="muted text-sm">
          Overlay of the bowling-side and non-bowling knee interior angle across the delivery.
        </p>
      </div>
      <div style={{ height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis dataKey="frame" stroke="#91aeca" fontSize={11} />
            <YAxis stroke="#91aeca" fontSize={11} />
            <Tooltip
              contentStyle={{
                background: "#091522",
                border: "1px solid rgba(122, 164, 200, 0.22)",
                borderRadius: 12,
              }}
              formatter={(v) => `${Number(v).toFixed(1)}°`}
            />
            <Legend wrapperStyle={{ color: "#d9ecff", fontSize: 12 }} />
            <Line
              type="monotone"
              dataKey="left"
              stroke="#57f0ff"
              strokeWidth={2.2}
              dot={false}
              name="Left leg"
            />
            <Line
              type="monotone"
              dataKey="right"
              stroke="#ffbd59"
              strokeWidth={2.2}
              dot={false}
              name="Right leg"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
