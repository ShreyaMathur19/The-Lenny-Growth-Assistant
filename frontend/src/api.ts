import type { Artifact, Message, Session } from "./types";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body?.detail;
    throw new Error(detail?.message ?? detail?.code ?? `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  createSession: () => request<Session>("/sessions", { method: "POST", body: JSON.stringify({ user_id: "demo-user" }) }),
  listSessions: () => request<Session[]>("/sessions"),
  listMessages: (sessionId: string) => request<Message[]>(`/sessions/${sessionId}/messages`),
  listArtifacts: (sessionId: string) => request<Artifact[]>(`/sessions/${sessionId}/artifacts`),
  chat: (payload: {
    session_id: string;
    message: string;
    provider: "ollama" | "cloud";
    mode: "auto" | "qa" | "ship30" | "artifact";
    artifact_type: "markdown" | "html";
  }) => request<{ message: Message; mode: string; artifact: Artifact | null }>("/chat", { method: "POST", body: JSON.stringify(payload) }),
  health: () => request<{ status: string; database: string; ollama: string }>("/health")
};
