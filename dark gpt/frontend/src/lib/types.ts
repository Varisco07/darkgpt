/** Tipi condivisi con il backend FastAPI. */

export type ProjectMode = "PASSIVE" | "LAB" | "AUTHORIZED_ASSESSMENT";

export type FindingStatus =
  | "INFO"
  | "POTENTIAL"
  | "NEEDS_VALIDATION"
  | "CONFIRMED"
  | "FALSE_POSITIVE"
  | "FIXED";

export type FindingSeverity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ToolRunStatus =
  | "SUCCESS"
  | "FAILED"
  | "TIMEOUT"
  | "UNAVAILABLE"
  | "DENIED"
  | "INVALID_INPUT";

export interface Project {
  id: number;
  name: string;
  description: string;
  mode: ProjectMode;
  stack: string[];
  root_path: string;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSummary {
  project: Project;
  findings_total: number;
  findings_confirmed: number;
  findings_open: number;
  assets_in_scope: number;
  tool_runs: number;
}

export interface Evidence {
  id: number;
  finding_id: number;
  kind: string;
  payload: string;
  observed: string;
  source: string;
  created_at: string;
}

export interface StateChange {
  id: number;
  finding_id: number;
  from_status: FindingStatus;
  to_status: FindingStatus;
  reason: string;
  actor: string;
  created_at: string;
}

export interface Finding {
  id: number;
  project_id: number;
  title: string;
  category: string;
  component: string;
  status: FindingStatus;
  severity: FindingSeverity;
  confidence: number;
  cvss_score: number | null;
  cvss_vector: string;
  hypothesis: string;
  impact: string;
  remediation: string;
  location: string;
  cwe: string;
  owasp: string;
  created_at: string;
  updated_at: string;
  evidences: Evidence[];
  state_changes: StateChange[];
}

export interface ScopeRule {
  id: number;
  kind: string;
  effect: "ALLOW" | "DENY";
  pattern: string;
  technique: string;
  notes: string;
}

export interface ScopeAsset {
  id: number;
  kind: string;
  value: string;
  allowed: boolean;
  technique: string;
  notes: string;
}

export interface ScopePolicy {
  id: number;
  project_id: number;
  raw_text: string;
  notes: string;
  asset_count: number;
  prohibited_techniques: string[];
  rules: ScopeRule[];
  assets: ScopeAsset[];
  created_at: string;
}

export interface ScopeCheck {
  decision: "ALLOWED" | "OUT_OF_SCOPE" | "DENIED" | "LAB_ALLOWED";
  reason: string;
  matched_rule_id: number | null;
  matched_pattern: string | null;
  requires_confirmation: boolean;
  prohibited: string[];
}

export interface ToolDescribe {
  name: string;
  category: string;
  description: string;
  input_schema: Record<string, unknown>;
  requires_scope: boolean;
  mutating: boolean;
  timeout_seconds: number;
  technique: string;
  install_hint: string;
  in_process: boolean;
  availability: "available" | "unavailable" | "degraded";
  availability_reason: string;
  version: string;
}

export interface ToolRunResult {
  status: ToolRunStatus;
  tool: string;
  output: unknown;
  output_text: string;
  error: string;
  duration_ms: number;
  exit_code: number | null;
  run_id: number | null;
  details: Record<string, unknown>;
}

export interface ToolRun {
  id: number;
  project_id: number;
  tool_name: string;
  status: ToolRunStatus;
  input_json: Record<string, unknown>;
  output_text: string;
  output_hash: string;
  exit_code: number | null;
  duration_ms: number;
  error_text: string;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  project_id: number;
  role: string;
  content: string;
  tool_calls: Record<string, unknown>;
  simulated: boolean;
  created_at: string;
}

export interface ChatHistory {
  project_id: number;
  messages: ChatMessage[];
  provider: string;
  provider_configured: boolean;
}

export interface Report {
  id: number;
  project_id: number;
  format: "MARKDOWN" | "HTML" | "JSON";
  content: string;
  created_at: string;
}

export interface Health {
  status: string;
  version: string;
  database: string;
  llm_provider: string;
  llm_configured: boolean;
  tools_available: number;
  tools_total: number;
}

export interface LlmStatus {
  provider: string;
  base_url: string;
  model: string;
  api_key_set: boolean;
  configured: boolean;
  temperature: number;
  max_tokens: number;
  timeout: number;
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}
