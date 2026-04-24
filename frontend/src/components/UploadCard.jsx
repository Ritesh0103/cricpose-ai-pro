import { useRef, useState } from "react";
import { Upload, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";

const ACCEPTED = "video/mp4,video/quicktime,video/webm,video/x-m4v,video/mpeg";

export default function UploadCard({ onComplete }) {
  const fileInput = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("idle"); // idle | uploading | analyzing | done
  const [error, setError] = useState(null);

  const pickFile = (selected) => {
    if (!selected) return;
    setError(null);
    setFile(selected);
  };

  const start = async () => {
    if (!file) return;
    setStage("uploading");
    setProgress(0);
    setError(null);
    try {
      const result = await api.uploadVideo(file, (p) => {
        setProgress(p);
        if (p >= 100) setStage("analyzing");
      });
      setStage("done");
      onComplete?.(result);
    } catch (err) {
      setError(err.message);
      setStage("idle");
    }
  };

  return (
    <div className="panel" data-testid="upload-card">
      <div className="flex flex-wrap justify-between gap-4 mb-4">
        <div>
          <h2 className="text-lg font-semibold">Video Upload Analyzer</h2>
          <p className="muted text-sm">
            Drop a bowling clip to run MediaPipe pose detection and research-grade biomechanics scoring.
          </p>
        </div>
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
        <p className="muted text-sm">Accepted: mp4, mov, webm, m4v</p>
        <div className="flex justify-center gap-3 mt-5">
          <Button
            variant="outline"
            className="btn-outline-brand"
            onClick={() => fileInput.current?.click()}
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
          <div className="text-xs uppercase tracking-[0.18em] muted">Selected video</div>
          <div className="font-semibold truncate">{file.name}</div>
          <div className="muted text-sm">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
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
            Running MediaPipe pose detection and biomechanics scoring — this takes 20-60s depending on clip length.
          </p>
        </div>
      ) : null}

      {error ? (
        <p className="text-[var(--danger)] text-sm mt-3" data-testid="upload-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
