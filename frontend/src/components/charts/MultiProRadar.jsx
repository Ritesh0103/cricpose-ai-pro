import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

/**
 * Overlay radar chart — athlete vs N pro bowlers on the same axes.
 */
const PRO_PALETTE = ["#ffbd59", "#ff7575", "#c1f257", "#d7a7ff", "#f4c15d", "#7af2c8", "#6fb1ff"];

export default function MultiProRadar({ athleteMetrics = {}, pros = [] }) {
  if (!athleteMetrics || !pros.length) {
    return (
      <div className="panel" data-testid="multi-pro-radar">
        <p className="muted text-sm">Pick at least one pro bowler to overlay.</p>
      </div>
    );
  }
  const keys = [
    ["release_angle", "Release angle"],
    ["front_knee_brace", "Front brace"],
    ["shoulder_alignment", "Shoulder align"],
    ["hip_rotation", "Hip sep."],
    ["bowling_arm_speed", "Arm speed"],
    ["follow_through_balance", "Balance"],
    ["runup_consistency", "Run-up cons."],
    ["overall_efficiency", "Efficiency"],
  ];
  const data = keys.map(([key, label]) => {
    const row = { subject: label, You: athleteMetrics[key] || 0 };
    pros.forEach((p) => {
      row[p.name] = p.metrics?.[key] ?? 0;
    });
    return row;
  });
  return (
    <div className="panel" data-testid="multi-pro-radar">
      <div className="mb-3">
        <h3 className="text-base font-semibold">You vs selected pros</h3>
        <p className="muted text-sm">
          Weighted biomechanics shape overlay across eight signals.
        </p>
      </div>
      <div style={{ height: 360 }}>
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
            <Legend wrapperStyle={{ color: "#d9ecff", fontSize: 12 }} />
            <Radar name="You" dataKey="You" stroke="#57f0ff" fill="#57f0ff" fillOpacity={0.35} strokeWidth={2} />
            {pros.map((p, i) => (
              <Radar
                key={p.name}
                name={p.name}
                dataKey={p.name}
                stroke={PRO_PALETTE[i % PRO_PALETTE.length]}
                fill={PRO_PALETTE[i % PRO_PALETTE.length]}
                fillOpacity={0.16}
                strokeWidth={1.8}
              />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
