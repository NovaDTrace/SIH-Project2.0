import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const API = `${BASE}/api`;

export const api = axios.create({ baseURL: API, timeout: 120_000 });

export const loadPreset = () => api.post("/dataset/load-preset").then((r) => r.data);
export const uploadCsv = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/dataset/upload", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  }).then((r) => r.data);
};
export const trainModel = (session_id, window = 20, n_estimators = 60) =>
  api.post("/pipeline/train", { session_id, window, n_estimators }).then((r) => r.data);
export const simulate = (session_id, blackout_start_s, blackout_end_s) =>
  api.post("/pipeline/simulate", { session_id, blackout_start_s, blackout_end_s }).then((r) => r.data);
export const aiSummary = (session_id) =>
  api.post("/ai/summary", { session_id }).then((r) => r.data);
