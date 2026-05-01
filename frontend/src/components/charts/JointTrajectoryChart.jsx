import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

/**
 * Joint trajectory scatter — plots the bowling wrist x,y (normalised) frame by frame.
 * Color encodes time (earlier frames are dimmer).
 */
export default function JointTrajectoryChart({ data = [] }) {
  const enriched = data.map((p, i) => ({ ...p, intensity: i / Math.max(1, data.length - 1) }));
  return (
    <div className="panel" data-testid="chart-joint-trajectory">
      <div className="mb-3">
        <h3 className="text-base font-semibold">Bowling wrist trajectory</h3>
        <p className="muted text-sm">
          Normalised x/y position of the bowling wrist per frame — ideal deliveries trace a smooth
          arc.
        </p>
      </div>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" strokeDasharray="3 3" />
            <XAxis type="number" dataKey="x" name="x" domain={[0, 100]} stroke="#91aeca" fontSize={11} />
            <YAxis type="number" dataKey="y" name="y" domain={[0, 100]} stroke="#91aeca" fontSize={11} />
            <ZAxis type="number" dataKey="intensity" range={[40, 180]} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              contentStyle={{
                background: "#091522",
                border: "1px solid rgba(122, 164, 200, 0.22)",
                borderRadius: 12,
              }}
              formatter={(value, name) => [`${value}`, name]}
              labelFormatter={() => ""}
            />
            <Scatter data={enriched} fill="#57f0ff" fillOpacity={0.8} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
