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
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

function extractError(err) {
  const detail = err?.response?.data?.detail;
  return new Error(formatApiErrorDetail(detail) || err.message || "Request failed");
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
  uploadVideo: async (file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await client.post("/analysis/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (e.total && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
        },
        timeout: 10 * 60 * 1000,
      });
      return data;
    } catch (err) {
      throw extractError(err);
    }
  },
  // Returns an object URL for a protected media endpoint (video/image).
  protectedBlobUrl: async (path) => {
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
