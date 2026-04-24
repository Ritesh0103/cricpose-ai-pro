import { Link } from "react-router-dom";
import { Bolt, ChartColumn, ScanSearch, ShieldCheck } from "lucide-react";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";

const FEATURES = [
  {
    title: "Real pose tracking",
    description:
      "OpenCV + MediaPipe extract 33 body landmarks per frame to reconstruct motion phases and key events from a single bowling clip.",
    icon: ScanSearch,
  },
  {
    title: "Research-grade biomechanics",
    description:
      "Front knee flexion at FFC and release, pelvis-shoulder separation, trunk lateral flexion, stride length, vGRF estimate, release speed and angle.",
    icon: ChartColumn,
  },
  {
    title: "Pro benchmark compare",
    description:
      "Weighted similarity against Bumrah, Starc, Shami, Lee, Anderson, Steyn with closest-match detection and coaching deltas.",
    icon: Bolt,
  },
  {
    title: "Secure session history",
    description:
      "Every analysis is stored against your account with PDF reports, processed overlay video, and re-comparisons any time.",
    icon: ShieldCheck,
  },
];

const METRICS = [
  { label: "Shoulder alignment", value: "9.4°" },
  { label: "Pelvis-shoulder sep.", value: "41.3°" },
  { label: "Front knee @ release", value: "168.6°" },
  { label: "Release speed (est.)", value: "137.2 kph" },
  { label: "Stride length", value: "1.84 m" },
  { label: "Peak vGRF", value: "5.1 BW" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen" data-testid="landing-page">
      <Navbar />
      <main className="page-shell">
        <section className="grid gap-8 md:grid-cols-[1.15fr_0.85fr] items-center min-h-[72vh] py-8">
          <div>
            <div className="eyebrow mb-3">Elite bowling intelligence</div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.05]">
              CricPose AI Pro turns a single bowling clip into a coaching-grade biomechanics report.
            </h1>
            <p className="muted mt-5 text-base md:text-lg max-w-2xl">
              Upload your delivery, detect body landmarks frame by frame, and surface release timing,
              front-leg brace, hip-shoulder separation, trunk flexion, vGRF, and release speed in a
              single modern analytics workflow.
            </p>
            <div className="flex flex-wrap gap-3 mt-7">
              <Link to="/analysis" data-testid="hero-start-analysis">
                <Button className="btn-brand h-12 px-6 text-base">Start analysis</Button>
              </Link>
              <Link to="/login" data-testid="hero-login">
                <Button variant="outline" className="btn-outline-brand h-12 px-6 text-base">
                  Login
                </Button>
              </Link>
            </div>
          </div>
          <div className="glass p-7" data-testid="hero-metric-card">
            <div className="stat-card mb-4">
              <div className="text-xs uppercase tracking-[0.18em] muted">Analysis stack</div>
              <div className="font-semibold mt-1">OpenCV + MediaPipe Pose + FastAPI</div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {METRICS.map((m) => (
                <div key={m.label} className="stat-card">
                  <div className="text-xs uppercase tracking-[0.18em] muted">{m.label}</div>
                  <div className="font-semibold mt-1">{m.value}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-14">
          <div className="mb-6">
            <div className="eyebrow">How it works</div>
            <h2 className="text-2xl md:text-3xl font-semibold">From upload to action intelligence</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            {[
              ["1. Upload video", "Drop an mp4, mov, or webm bowling clip and review before running."],
              ["2. Detect landmarks", "33 body points are tracked frame-by-frame to reconstruct motion."],
              ["3. Score mechanics", "Joint angles, FFC and release events, vGRF, stride, release speed."],
              ["4. Review dashboard", "Skeleton overlay, charts, risk flags, coaching tips, PDF report."],
            ].map(([title, desc]) => (
              <article key={title} className="panel">
                <h3 className="font-semibold mb-2">{title}</h3>
                <p className="muted text-sm">{desc}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-14">
          <div className="mb-6">
            <div className="eyebrow">Feature suite</div>
            <h2 className="text-2xl md:text-3xl font-semibold">Built for serious bowling analysis</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            {FEATURES.map((f) => (
              <article key={f.title} className="panel" data-testid={`feature-${f.title.toLowerCase().replace(/\s+/g, "-")}`}>
                <f.icon className="w-6 h-6 text-[var(--accent)] mb-3" />
                <h3 className="font-semibold mb-2">{f.title}</h3>
                <p className="muted text-sm">{f.description}</p>
              </article>
            ))}
          </div>
        </section>

        <footer className="mt-16 mb-6 text-sm muted">
          © {new Date().getFullYear()} CricPose AI Pro · Single-camera estimates — architecture ready
          for multi-camera and radar ground-truth upgrades.
        </footer>
      </main>
    </div>
  );
}
