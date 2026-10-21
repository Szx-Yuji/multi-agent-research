const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "mar.token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // private mode, or storage blocked
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Non-fatal: the session just will not survive a reload.
  }
}

export { API_URL };

function detailToMessage(data) {
  const d = data?.detail;
  if (typeof d === "string") return d;
  // FastAPI validation errors arrive as a list of objects.
  if (Array.isArray(d) && d.length) return d[0].msg ?? "Invalid input";
  return null;
}

async function request(path, { method = "GET", body, auth = false } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  const token = auth ? getToken() : null;
  if (token) headers.Authorization = "Bearer " + token;

  const res = await fetch(API_URL + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(detailToMessage(data) || "Request failed (" + res.status + ")");
  }
  return data;
}

export const api = {
  register: (email, password) =>
    request("/api/auth/register", { method: "POST", body: { email, password } }),
  login: (email, password) =>
    request("/api/auth/login", { method: "POST", body: { email, password } }),
  me: () => request("/api/auth/me", { auth: true }),
  history: () => request("/api/history", { auth: true }),
  historyItem: (id) => request("/api/history/" + id, { auth: true }),
  deleteHistoryItem: (id) =>
    request("/api/history/" + id, { method: "DELETE", auth: true }),
  startResearch: (query) =>
    request("/api/research", { method: "POST", body: { query }, auth: true }),
};
