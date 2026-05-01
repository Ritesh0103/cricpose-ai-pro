import { useRef, useState } from "react";
import { AlertCircle, Play, RotateCw, Upload, Video, Zap } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";

const ACCEPTED = "video/mp4,video/quicktime,video/webm,video/x-m4v,video/mpeg";
const ACCEPTED_SET = new Set([
  "video/mp4",
  "video/quicktime",
  "video/webm",
  "video/x-m4v",
  "video/mpeg",
]);
const MAX_MB = 200;

export default function UploadCard({ onComplete }) {
  const fileInput = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("idle"); // idle | uploading | analyzing | done
  const [error, setError] = useState(null);
  const [demoLoading, setDemoLoading] = useState(false);

  const pickFile = (selected) => {
    if (!selected) return;
    setError(null);
    // Client-side validation for clearer feedback before hitting the network.
    const sizeMB = selected.size / (1024 * 1024);
    if (sizeMB > MAX_MB) {
      const msg = `File is ${sizeMB.toFixed(1)} MB — please upload a clip under ${MAX_MB} MB.`;
      setError(msg);
      toast.error(msg);
      return;
    }
    const ct = selected.type;
    if (ct && !ACCEPTED_SET.has(ct)) {
      const msg = `"${ct}" is not supported. Please use mp4, mov, webm, or m4v.`;
      setError(msg);
      toast.error(msg);
      return;
    }
    setFile(selected);
    toast.success(`Selected "${selected.name}" (${sizeMB.toFixed(1)} MB)`);
  };

  const start = async () => {
    if (!file) return;
    setStage("uploading");
    setProgress(0);
    setError(null);
    try {
      const result = await api.uploadVideo(
        file,
        (p) => setProgress(p),
        (s) => setStage(s),
      );
      setStage("done");
      toast.success("Analysis ready — scroll down for your report.");
      onComplete?.(result);
    } catch (err) {
      const msg = err?.message || "Upload failed. Please try again.";
      setError(msg);
      toast.error(msg);
      setStage("idle");
    }
  };

  const runDemo = async () => {
    setDemoLoading(true);
    setError(null);
    try {
      const result = await api.runDemo();
      toast.success("Demo analysis ready — exploring the full dashboard with synthetic metrics.");
      onComplete?.(result);
    } catch (err) {
      const msg = err?.message || "Demo mode failed. Please retry.";
      setError(msg);
      toast.error(msg);
    } finally {
      setDemoLoading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setError(null);
    setStage("idle");
    setProgress(0);
  };

  return (
    <div className="panel" data-testid="upload-card">
      <div className="flex flex-wrap justify-between gap-4 mb-4">
        <div>
          <h2 className="text-lg font-semibold">Video Upload Analyzer</h2>
          <p className="muted text-sm">
            Drop a bowling clip to run MediaPipe pose detection and research-grade biomechanics
            scoring. No clip handy? Tap Demo mode to explore a full sample report.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          className="btn-outline-brand"
          onClick={runDemo}
          disabled={demoLoading || stage === "uploading" || stage === "analyzing"}
          data-testid="demo-mode-btn"
        >
          <Zap className="w-4 h-4 mr-2" /> {demoLoading ? "Generating…" : "Try demo mode"}
        </Button>
      </div>

      <div
        className={`rounded-xl border border-dashed border-[var(--line)] bg-[var(--bg-soft)] py-10 px-6 text-center transition-colors ${
          dragging ? "ring-2 ring-[var(--accent)]" : ""
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pickFile(e.dataTransfer.files?.[0]);
        }}
        data-testid="upload-dropzone"
      >
        <Video className="mx-auto w-9 h-9 text-[var(--accent)]" />
        <h3 className="mt-3 text-base font-semibold">Drop your bowling delivery here</h3>
        <p className="muted text-sm">
          Accepted: mp4, mov, webm, m4v · max {MAX_MB} MB · 5–20s clips work best
        </p>
        <div className="flex justify-center gap-3 mt-5 flex-wrap">
          <Button
            variant="outline"
            className="btn-outline-brand"
            onClick={() => fileInput.current?.click()}
            disabled={stage === "uploading" || stage === "analyzing"}
            data-testid="choose-video-btn"
          >
            <Upload className="w-4 h-4 mr-2" /> Choose video
          </Button>
          <Button
            className="btn-brand"
            disabled={!file || stage === "uploading" || stage === "analyzing"}
            onClick={start}
            data-testid="start-analysis-btn"
          >
            <Play className="w-4 h-4 mr-2" />
            {stage === "uploading"
              ? "Uploading…"
              : stage === "analyzing"
                ? "Analyzing…"
                : "Start analysis"}
          </Button>
        </div>
        <input
          ref={fileInput}
          hidden
          type="file"
          accept={ACCEPTED}
          onChange={(e) => pickFile(e.target.files?.[0])}
          data-testid="video-input"
        />
      </div>

      {file ? (
        <div className="stat-card mt-4" data-testid="selected-file">
          <div className="flex justify-between items-start">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] muted">Selected video</div>
              <div className="font-semibold truncate">{file.name}</div>
              <div className="muted text-sm">
                {(file.size / 1024 / 1024).toFixed(2)} MB · {file.type || "video"}
              </div>
            </div>
            {stage === "idle" ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="btn-outline-brand"
                onClick={reset}
                data-testid="clear-file-btn"
              >
                Clear
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {stage === "uploading" ? (
        <div className="mt-4" data-testid="upload-progress">
          <Progress value={progress} />
          <p className="muted text-sm mt-1">Uploading… {progress}%</p>
        </div>
      ) : null}

      {stage === "analyzing" ? (
        <div className="mt-4" data-testid="analysis-progress">
          <Progress value={99} />
          <p className="muted text-sm mt-1">
            Running MediaPipe pose detection and biomechanics scoring in the background — this
            typically takes 20–90s depending on clip length. Hang tight, we're polling for results…
          </p>
        </div>
      ) : null}

      {error ? (
        <div
          className="mt-4 stat-card border-[rgba(255,117,117,0.4)] flex gap-3 items-start"
          data-testid="upload-error"
        >
          <AlertCircle className="w-5 h-5 text-[var(--danger)] flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-xs uppercase tracking-[0.18em] text-[var(--danger)] font-semibold">
              Something stopped the analysis
            </div>
            <p className="text-sm mt-1 text-[var(--text)]">{error}</p>
            <p className="muted text-xs mt-2">
              Tip: a 5–20s side-on delivery clip with the full bowler in frame works best. If the
              upload keeps timing out, try Demo mode to preview the dashboard.
            </p>
            {file ? (
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  className="btn-brand"
                  onClick={start}
                  disabled={stage === "uploading" || stage === "analyzing"}
                  data-testid="retry-upload-btn"
                >
                  <RotateCw className="w-4 h-4 mr-2" /> Retry
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="btn-outline-brand"
                  onClick={runDemo}
                  disabled={demoLoading}
                  data-testid="demo-from-error-btn"
                >
                  <Zap className="w-4 h-4 mr-2" />
                  {demoLoading ? "Loading…" : "Try demo instead"}
                </Button>
              </div>
            ) : (
              <div className="flex gap-2 mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  className="btn-outline-brand"
                  onClick={() => fileInput.current?.click()}
                  data-testid="retry-upload-btn"
                >
                  <Upload className="w-4 h-4 mr-2" /> Choose another file
                </Button>
                <Button
                  size="sm"
                  className="btn-brand"
                  onClick={runDemo}
                  disabled={demoLoading}
                  data-testid="demo-from-error-btn"
                >
                  <Zap className="w-4 h-4 mr-2" />
                  {demoLoading ? "Loading…" : "Try demo instead"}
                </Button>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
