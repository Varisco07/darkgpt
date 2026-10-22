/**
 * Client HTTP verso il backend DarkGPT.
 *
 * Tutte le chiamate passano dal server Next.js (nessuna CORS dal browser) e
 * usano la stessa base URL configurata in `next.config.mjs`.
 */

import type {
  ChatHistory,
  ChatMessage,
  Finding,
  FindingSeverity,
  FindingStatus,
  Health,
  LlmStatus,
  Project,
  ProjectMode,
  ProjectSummary,
  Report,
  ScopeCheck,
  ScopePolicy,
  ToolDescribe,
  ToolRun,
  ToolRunResult,
} from "./types";

const DEFAULT_BASE = "http://127.0.0.1:8000";

/** Timeout delle chiamate al backend, in millisecondi. */
const REQUEST_TIMEOUT_MS = 15_000;

/**
 * Endpoint del backend, letto a ogni richiesta.
 *
 * La lettura avviene a runtime (non a livello di modulo) perche' l'endpoint
 * puo' cambiare senza una nuova build: lo stesso bundle serve sviluppo,
 * staging e produzione.
 */
function baseUrl(): string {
  return process.env.DARKGPT_API_URL || DEFAULT_BASE;
}

export class BackendError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(
    message: string,
    code: string,
    status: number,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "BackendError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, {
    ...init,
    // Timeout obbligatorio: senza, una build o un render su backend
    // irraggiungibile resterebbe appeso indefinitamente.
    signal: init?.signal ?? AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    // Nessun caching: la dashboard mostra sempre lo stato corrente del backend.
    cache: "no-store",
  });

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const payload = body as {
      error?: { code: string; message: string; details?: Record<string, unknown> };
    };
    const error = payload?.error;
    throw new BackendError(
      error?.message ?? `Errore HTTP ${response.status}`,
      error?.code ?? "http_error",
      response.status,
      error?.details ?? {},
    );
  }

  return body as T;
}

export const api = {
  // -- sistema ---------------------------------------------------------
  health: () => request<Health>("/health"),
  llmStatus: () => request<LlmStatus>("/api/settings/llm"),
  limits: () => request<Record<string, number | string>>("/api/settings/limits"),
  logs: (limit = 100) => request<unknown[]>(`/api/logs?limit=${limit}`),
  overview: () => request<Record<string, unknown>>("/api/overview"),

  // -- progetti --------------------------------------------------------
  listProjects: () => request<Project[]>("/api/projects"),
  getProject: (id: number) => request<Project>(`/api/projects/${id}`),
  createProject: (payload: {
    name: string;
    description?: string;
    mode?: ProjectMode;
    stack?: string[];
    root_path?: string;
  }) =>
    request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProject: (id: number, payload: Partial<Project>) =>
    request<Project>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  setProjectMode: (id: number, mode: ProjectMode) =>
    request<Project>(`/api/projects/${id}/mode`, {
      method: "PATCH",
      body: JSON.stringify({ mode }),
    }),
  projectSummary: (id: number) => request<ProjectSummary>(`/api/projects/${id}/summary`),

  // -- scope -----------------------------------------------------------
  getScope: (projectId: number) =>
    request<ScopePolicy | null>(`/api/projects/${projectId}/scope`),
  importScope: (projectId: number, text: string, notes = "") =>
    request<ScopePolicy>(`/api/projects/${projectId}/scope/import`, {
      method: "POST",
      body: JSON.stringify({ text, notes }),
    }),
  addScopeRule: (
    projectId: number,
    payload: {
      kind: string;
      effect: string;
      pattern: string;
      technique?: string;
      notes?: string;
    },
  ) =>
    request<unknown>(`/api/projects/${projectId}/scope/rules`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  checkScope: (projectId: number, target: string, technique = "") =>
    request<ScopeCheck>(`/api/projects/${projectId}/scope/check`, {
      method: "POST",
      body: JSON.stringify({ target, technique }),
    }),

  // -- finding ---------------------------------------------------------
  listFindings: (
    projectId: number,
    filters?: { status?: FindingStatus; severity?: FindingSeverity },
  ) => {
    const params = new URLSearchParams();
    if (filters?.status) params.set("status", filters.status);
    if (filters?.severity) params.set("severity", filters.severity);
    const query = params.toString();
    return request<Finding[]>(`/api/projects/${projectId}/findings${query ? `?${query}` : ""}`);
  },
  createFinding: (
    projectId: number,
    payload: {
      title: string;
      category?: string;
      component?: string;
      severity?: FindingSeverity;
      confidence?: number;
      hypothesis?: string;
      impact?: string;
      remediation?: string;
      location?: string;
      cwe?: string;
      owasp?: string;
    },
  ) =>
    request<Finding>(`/api/projects/${projectId}/findings`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  transitionFinding: (
    projectId: number,
    findingId: number,
    payload: {
      status: FindingStatus;
      reason: string;
      evidence?: {
        kind: string;
        payload?: string;
        observed?: string;
        source?: string;
      }[];
    },
  ) =>
    request<Finding>(`/api/projects/${projectId}/findings/${findingId}/transition`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  addEvidence: (
    projectId: number,
    findingId: number,
    payload: { kind: string; payload?: string; observed?: string; source?: string },
  ) =>
    request<unknown>(`/api/projects/${projectId}/findings/${findingId}/evidence`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // -- tool ------------------------------------------------------------
  listTools: () => request<ToolDescribe[]>("/api/tools"),
  runTool: (
    projectId: number,
    payload: {
      tool: string;
      input: Record<string, unknown>;
      confirm?: boolean;
      target?: string;
      technique?: string;
    },
  ) =>
    request<ToolRunResult>(`/api/projects/${projectId}/scans`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listToolRuns: (projectId: number) =>
    request<ToolRun[]>(`/api/projects/${projectId}/tool-runs`),

  // -- chat ------------------------------------------------------------
  chatHistory: (projectId: number) =>
    request<ChatHistory>(`/api/projects/${projectId}/chat`),
  sendChat: (projectId: number, message: string, role = "analysis") =>
    request<ChatMessage>(`/api/projects/${projectId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, role }),
    }),

  // -- report ----------------------------------------------------------
  listReports: (projectId: number) =>
    request<Report[]>(`/api/projects/${projectId}/reports`),
  createReport: (projectId: number, format: "MARKDOWN" | "HTML" | "JSON") =>
    request<Report>(`/api/projects/${projectId}/reports?format=${format}`, {
      method: "POST",
    }),
};
