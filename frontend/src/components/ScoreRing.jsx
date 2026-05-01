export default function ScoreRing({ value = 0, label }) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const safe = Math.max(0, Math.min(100, Number(value) || 0));
  const offset = circumference - (safe / 100) * circumference;
  return (
    <div className="stat-card flex items-center gap-4" data-testid={`score-ring-${label?.toLowerCase()}`}>
      <div className="relative w-[110px] h-[110px]">
        <svg width="110" height="110" className="-rotate-90">
          <circle cx="55" cy="55" r={radius} stroke="rgba(255,255,255,0.08)" strokeWidth="10" fill="none" />
          <circle
            cx="55"
            cy="55"
            r={radius}
            stroke="url(#ringGrad)"
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
          <defs>
            <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#57f0ff" />
              <stop offset="100%" stopColor="#86ff9f" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="text-xl font-semibold">{safe.toFixed(1)}</div>
            <div className="text-xs muted">out of 100</div>
          </div>
        </div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.18em] muted">Score</div>
        <div className="text-lg font-semibold">{label}</div>
      </div>
    </div>
  );
}
