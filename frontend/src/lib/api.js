import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API_BASE = `${BACKEND_URL}/api`;

const STORAGE_KEY = "cricpose-auth";

export function getStoredSession() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.token) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveSession(token, user) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user }));
}

export function clearSession() {
  window.localStorage.removeItem(STORAGE_KEY);
}

export function getToken() {
  return getStoredSession()?.token || null;
}

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

function extractError(err) {
  // 1. Structured FastAPI detail (preferred)
  const detail = err?.response?.data?.detail;
  const detailStr = formatApiErrorDetail(detail);
  if (detailStr) return new Error(detailStr);

  // 2. HTTP status without detail — use status + statusText (e.g. 413 Payload Too Large)
  const status = err?.response?.status;
  if (status) {
    const statusText = err?.response?.statusText || "";
    const body = err?.response?.data;
    const bodyStr =
      typeof body === "string" && body.length < 400 ? ` — ${body.slice(0, 300)}` : "";
    if (status === 413) {
      return new Error("Video too large — please upload a clip under 200 MB.");
    }
    if (status === 504 || status === 502) {
      return new Error(
        "The analysis took too long and the gateway timed out. Try a shorter clip (under 20s) or the demo mode.",
      );
    }
    if (status === 401) {
      return new Error("Your session expired. Please sign in again.");
    }
    if (status === 415) {
      return new Error("Unsupported video format. Please upload mp4, mov, webm, or m4v.");
    }
    return new Error(
      `Request failed (${status}${statusText ? ` ${statusText}` : ""})${bodyStr || ""}`,
    );
  }

  // 3. No response — network or timeout error
  if (err?.code === "ECONNABORTED" || /timeout/i.test(err?.message || "")) {
    return new Error(
      "Upload/analysis timed out. Try a shorter clip (under 20s) or retry once — the server may be waking up.",
    );
  }
  if (err?.message === "Network Error") {
    return new Error(
      "Network error — couldn't reach the analysis server. Check your connection and retry.",
    );
  }
  return new Error(err?.message || "Request failed. Please try again.");
}

export const api = {
  signup: async (full_name, email, password) => {
    try {
      const { data } = await client.post("/auth/signup", { full_name, email, password });
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  login: async (email, password) => {
    try {
      const { data } = await client.post("/auth/login", { email, password });
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  guest: async () => {
    try {
      const { data } = await client.post("/auth/guest");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  me: async () => {
    try {
      const { data } = await client.get("/auth/me");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  logout: async () => {
    try {
      await client.post("/auth/logout");
    } catch {
      /* best-effort */
    }
  },
  dashboard: async () => {
    try {
      const { data } = await client.get("/users/dashboard");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  reports: async () => {
    try {
      const { data } = await client.get("/reports");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  report: async (id) => {
    try {
      const { data } = await client.get(`/reports/${id}`);
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  compareProfiles: async () => {
    try {
      const { data } = await client.get("/compare/profiles");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  compare: async ({ analysis_id, target_bowler, comparison_group }) => {
    try {
      const { data } = await client.post("/compare", {
        analysis_id,
        target_bowler: target_bowler || null,
        comparison_group: comparison_group || "closest",
      });
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  pipelineBowlers: async () => {
    try {
      const { data } = await client.get("/pipeline/bowlers");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  pipelineProcessAll: async (sampleFps = 8) => {
    try {
      const { data } = await client.post(`/pipeline/process-all?sample_fps=${sampleFps}`);
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  pipelineBuildProfiles: async () => {
    try {
      const { data } = await client.post("/pipeline/build-profiles");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  pipelineAnalyze: async (file, selectedBowlers = [], sampleFps = 8) => {
    const form = new FormData();
    form.append("file", file);
    form.append("selected_bowlers", JSON.stringify(selectedBowlers));
    try {
      const { data } = await client.post(`/pipeline/analyze?sample_fps=${sampleFps}`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 15 * 60 * 1000,
      });
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  uploadVideo: async (file, onProgress, onStage) => {
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await client.post("/analysis/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
          if (e.total && e.loaded >= e.total && onStage) onStage("analyzing");
        },
        timeout: 15 * 60 * 1000,
      });
      // Backend now returns immediately with status="processing" and runs the heavy
      // MediaPipe + PDF work in a background task. Poll until it flips to done/failed.
      if (data?.status === "processing" && data?.id) {
        if (onStage) onStage("analyzing");
        return await api.pollAnalysis(data.id, onStage);
      }
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  pollAnalysis: async (reportId, onStage, { intervalMs = 2000, timeoutMs = 10 * 60 * 1000 } = {}) => {
    const deadline = Date.now() + timeoutMs;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (Date.now() > deadline) {
        throw new Error(
          "Analysis is taking unusually long. Your report is saved under History — check back in a minute.",
        );
      }
      try {
        const { data } = await client.get(`/analysis/${reportId}/status`);
        if (data?.status === "done") {
          if (onStage) onStage("done");
          return data;
        }
        if (data?.status === "failed") {
          throw new Error(data.error || "Analysis failed. Please try again.");
        }
      } catch (err) {
        // Only re-throw if it's a real error; transient 5xx should keep polling briefly.
        const status = err?.response?.status;
        if (status === 401 || status === 404) throw extractError(err);
        if (!status) throw extractError(err);
        // Any other status — continue polling
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  },
  runDemo: async () => {
    try {
      const { data } = await client.post("/analysis/demo");
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  // Returns an object URL for a protected media endpoint (video/image).
  protectedBlobUrl: async (path) => {
    if (/^https?:\/\//i.test(path)) return path;
    const token = getToken();
    const response = await fetch(`${BACKEND_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(`Failed to fetch media (${response.status})`);
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },
  downloadFile: async (path, filename) => {
    const token = getToken();
    const response = await fetch(`${BACKEND_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) throw new Error(`Failed to download (${response.status})`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    try {
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      link.remove();
    } finally {
      URL.revokeObjectURL(url);
    }
  },
  downloadCSV: async (reportId, kind) => {
    const suffix = `${kind}`;
    await api.downloadFile(
      `/api/analysis/${reportId}/csv/${kind}`,
      `cricpose-${suffix}-${reportId.slice(0, 8)}.csv`,
    );
  },
};
