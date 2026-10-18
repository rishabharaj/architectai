import { auth, demoMode } from "./firebase";
import type { ChatMessage, Project } from "./types";

const base = (import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "")).replace(/\/$/, "");

async function headers(): Promise<HeadersInit> {
  const values: Record<string, string> = { "Content-Type": "application/json" };
  if (!demoMode) {
    const user = auth?.currentUser;
    if (!user) throw new Error("Sign in to continue");
    values.Authorization = `Bearer ${await user.getIdToken()}`;
  }
  return values;
}

async function request<T>(path: string, method = "GET", body?: object): Promise<T> {
  const response = await fetch(`${base}${path}`, { method, headers: await headers(), body: body ? JSON.stringify(body) : undefined });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; mode: string; ai_configured: boolean }>("/api/health"),
  projects: () => request<Project[]>("/api/projects"),
  create: (idea: string) => request<Project>("/api/projects", "POST", { idea }),
  get: (id: string) => request<Project>(`/api/projects/${id}`),
  answer: (id: string, question_id: string, selection: string) => request<Project>(`/api/projects/${id}/answers`, "POST", { question_id, selection }),
  category: (id: string, category: string) => request<Project>(`/api/projects/${id}/categories`, "POST", { category }),
  guide: (id: string) => request<Project>(`/api/projects/${id}/guide`, "POST"),
  rename: (id: string, name: string) => request<Project>(`/api/projects/${id}`, "PATCH", { name }),
  delete: (id: string) => request<void>(`/api/projects/${id}`, "DELETE"),
  messages: (id: string) => request<ChatMessage[]>(`/api/projects/${id}/messages`),
  clearMessages: (id: string) => request<void>(`/api/projects/${id}/messages`, "DELETE"),
  streamChat: async (id: string, message: string, onDelta: (text: string) => void) => {
    const response = await fetch(`${base}/api/projects/${id}/chat`, { method: "POST", headers: await headers(), body: JSON.stringify({ message }) });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Chat failed (${response.status})`);
    }
    if (!response.body) throw new Error("Chat stream is unavailable");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (const frame of frames) {
        const line = frame.split("\n").find((item) => item.startsWith("data: "));
        if (!line) continue;
        const event = JSON.parse(line.slice(6));
        if (event.type === "delta") onDelta(event.text);
        if (event.type === "error") throw new Error(event.message);
      }
    }
  },
  download: async (id: string, format: "md" | "pdf") => {
    const response = await fetch(`${base}/api/projects/${id}/export?format=${format}`, { headers: await headers() });
    if (!response.ok) throw new Error("Export failed");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `architect-${id.slice(0, 8)}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  },
};
