export type ActionState = {
  enabled: boolean;
  reason: string | null;
};

export type ApplicationActions = {
  launch: ActionState;
  stop: ActionState;
  restart: ActionState;
  open_repository: ActionState;
  open_documentation: ActionState;
  open_url: ActionState;
  logs: ActionState;
  check_health: ActionState;
};

export type ApplicationStatus = {
  state: string;
  label: string;
  detail: string;
  ownership: "managed" | "external" | "none" | "unknown";
  observed_at: string | null;
  stale: boolean;
  health_state: string | null;
  process_id: string | null;
};

export type LaunchDefinition = {
  id: string;
  application_id: string;
  name: string;
  launch_type: "none" | "command" | "server" | "url" | "editor";
  executable: string | null;
  arguments: string[];
  working_directory: string | null;
  env_names: string[];
  browser_url: string | null;
  health_type: "none" | "http" | "tcp" | "process";
  health_url: string | null;
  expected_port: number | null;
  is_primary: boolean;
  enabled: boolean;
  verified: boolean;
  verification_note: string;
  shutdown_behavior: string;
};

export type Application = {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  tags: string[];
  enabled: boolean;
  archived: boolean;
  pinned: boolean;
  display_order: number;
  repository_path: string | null;
  additional_paths: string[];
  working_directory: string | null;
  documentation_paths: string[];
  output_paths: string[];
  integration_adapter: string | null;
  adapter_enabled: boolean;
  adapter_config: Record<string, unknown>;
  related_projects: string[];
  related_books: string[];
  outcomes: string[];
  dependencies: string[];
  control_policy: { allow_launch: boolean; confirmation_required: boolean };
  source: string;
  notes: string;
  launch_definitions: LaunchDefinition[];
  status: ApplicationStatus;
  actions: ApplicationActions;
  last_launch_success_at: string | null;
  last_launch_failure_at: string | null;
  last_failure_detail: string | null;
  created_at: string;
  updated_at: string;
};

export type Repository = {
  id: string;
  name: string;
  path: string;
  classification: string;
  confidence: number;
  evidence: string[];
  role: string | null;
  source_root: string;
  is_git: boolean;
  branch: string | null;
  commit_hash: string | null;
  last_commit_at: string | null;
  dirty: boolean | null;
  accessible: boolean;
  candidate: boolean;
  last_observed_at: string | null;
  notes: string;
};

export type Checkpoint = {
  id: string;
  project_id: string;
  project_name: string | null;
  summary: string;
  last_completed: string;
  next_action: string;
  blockers: string;
  evidence_refs: string[];
  milestone: string;
  source: string;
  created_at: string;
};

export type Book = {
  id: string;
  project_id: string;
  project_name: string | null;
  title: string;
  status: string;
  current_milestone: string;
  next_action: string;
  manuscript_paths: string[];
  implementation_paths: string[];
  published_url: string | null;
  local_url: string | null;
  quality_review_state: string;
  last_activity_at: string | null;
  priority: number | null;
  latest_checkpoint: Checkpoint | null;
  repository_action: ActionState | null;
};

export type Outcome = {
  id: string;
  name: string;
  description: string;
  status: string;
  url: string | null;
  notes: string;
};

export type Project = {
  id: string;
  name: string;
  description: string;
  kind: string;
  status: string;
  priority: number;
  pinned: boolean;
  archived: boolean;
  display_order: number;
  current_milestone: string;
  next_action: string;
  notes: string;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
  repositories: Repository[];
  book: Book | null;
  outcomes: Outcome[];
  applications: Array<{ id: string; name: string; category: string }>;
  latest_checkpoint: Checkpoint | null;
  open_task_count: number;
  pending_recommendation_count: number;
};

export type Task = {
  id: string;
  project_id: string | null;
  project_name: string | null;
  title: string;
  description: string;
  status: string;
  priority: number;
  source: string;
  due_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Recommendation = {
  id: string;
  project_id: string | null;
  project_name: string | null;
  title: string;
  rationale: string;
  evidence: string[];
  source_application: string | null;
  source_ref: string | null;
  external_id: string | null;
  provenance: string;
  review_state: string;
  created_at: string;
  updated_at: string;
};

export type Decision = {
  id: string;
  project_id: string | null;
  project_name: string | null;
  title: string;
  rationale: string;
  status: string;
  source: string;
  decided_at: string;
  created_at: string;
};

export type ActivityEvent = {
  id: string;
  type: string;
  title: string;
  detail: string;
  project_id: string | null;
  project_name: string | null;
  application_id: string | null;
  application_name: string | null;
  process_id: string | null;
  source: string;
  source_id: string | null;
  evidence_ref: string | null;
  provenance: string;
  occurred_at: string;
  observed_at: string;
  metadata: Record<string, unknown>;
};

export type Adapter = {
  id: string;
  adapter: string;
  application_id: string | null;
  application_name: string | null;
  project_id: string | null;
  project_name: string | null;
  available: boolean;
  capabilities: string[];
  detail: string;
  error: string | null;
  last_checked_at: string | null;
  stale_after_seconds: number;
  stale: boolean;
};

export type BriefingItem = {
  rank: number;
  title: string;
  project_id: string | null;
  project_name: string | null;
  rationale: string;
  provenance: string;
  evidence: string[];
  source: string | null;
};

export type Briefing = {
  id: string;
  created_at: string;
  mode: string;
  provider: string | null;
  model: string | null;
  status: string;
  content: string;
  items: BriefingItem[];
  observations: Array<Record<string, unknown>>;
  error: string | null;
};

export type ProcessInstance = {
  id: string;
  application_id: string;
  application_name: string | null;
  launch_definition_id: string | null;
  pid: number | null;
  status: string;
  started_at: string;
  ended_at: string | null;
  exit_code: number | null;
  log_available: boolean;
  working_directory: string | null;
  command_preview: string | null;
  owned: boolean;
  reattached: boolean;
  error: string | null;
};

export type LogData = {
  process_id: string;
  lines: string[];
  truncated: boolean;
  path: string | null;
};

export type ProjectDetail = Project & {
  repository_action: ActionState | null;
  checkpoints: Checkpoint[];
  tasks: Task[];
  decisions: Decision[];
  recommendations: Recommendation[];
  activity: ActivityEvent[];
  adapters: Adapter[];
};

export type Dashboard = {
  generated_at: string;
  date: string;
  focus: Project | null;
  checkpoint: Checkpoint | null;
  books: Book[];
  applications: Application[];
  activity: ActivityEvent[];
  outcomes: Outcome[];
  tasks: Task[];
  recommendations: Recommendation[];
  adapters: Adapter[];
  briefing: Briefing | null;
  stats: Record<string, number>;
};

export type Resume = {
  project: Project | null;
  checkpoint: Checkpoint | null;
  recent_projects: Array<{ id: string; name: string; last_event_at: string }>;
};

export type Settings = {
  discovery: {
    exclusions: string[];
    max_depth: number;
    max_candidates: number;
    timeout_seconds: number;
    git_timeout_seconds: number;
  };
  editor: { command: string; arguments: string[]; append_path: boolean };
  browser: { open_mode: string };
  processes: {
    max_managed: number;
    health_check_interval_seconds: number;
    log_tail_lines: number;
  };
  adapters: { refresh_interval_minutes: number; timeout_seconds: number };
  retention: { activity_days: number; briefing_days: number; log_days: number };
  ai: {
    enabled: boolean;
    consent: boolean;
    provider: string;
    base_url: string;
    model: string;
    api_key_env: string;
    timeout_seconds: number;
  };
  startup: {
    profile_enabled: boolean;
    profile_applications: string[];
  };
  ui: { theme: string };
  discovery_roots: Array<{ path: string; enabled: boolean; added_at: string }>;
  ai_configured: boolean;
  ai_key_present: boolean;
};

export type DiscoveryScan = {
  scan_id: string | null;
  status: string;
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  roots: string[];
  counts: Record<string, number>;
  errors: Array<{ path: string; error: string }>;
  truncated: boolean;
  cancelled: boolean;
  scanned_directories: number;
  elapsed_seconds: number | null;
  candidate_count: number | null;
  excluded_count: number | null;
  skipped_links: string[];
  error: string | null;
};

export type Candidate = Repository;

export type Health = {
  status: string;
  version: string;
  database: string;
  schema_version: number;
  ai_enabled: boolean;
  monitor_enabled: boolean;
};

export type IntegrationAction = {
  id: string;
  title: string;
  description: string;
  risk: string;
  capability: string;
  approval_required: boolean;
  side_effect: string;
  parameters_schema: {
    type?: string;
    required?: string[];
    properties?: Record<string, { type?: string; description?: string; default?: unknown; minimum?: number; maximum?: number }>;
    additionalProperties?: boolean;
  };
  enabled: boolean;
  unavailable_reason: string | null;
};

export type Integration = {
  application_id: string;
  name: string;
  adapter: string;
  protocol_version: string;
  mode: string;
  enabled: boolean;
  available: boolean;
  detail: string;
  error: string | null;
  capabilities: string[];
  actions: IntegrationAction[];
  last_checked_at: string | null;
  resource_counts: Record<string, number>;
  repository_path: string | null;
  config: Record<string, unknown>;
  repositories: Array<{ path: string; name: string; source: string }>;
};

export type IntegrationDecision = {
  id: string;
  application_id: string;
  resource_type: string;
  external_id: string;
  decision: string;
  reason: string;
  sync_state: string;
  source_decision_id: string | null;
  decided_at: string;
  created_at: string;
};

export type IntegrationRecord = {
  id: string;
  application_id: string;
  application_name: string | null;
  resource_type: string;
  external_id: string;
  title: string;
  summary: string;
  state: string;
  project_id: string | null;
  project_name: string | null;
  source_version: string | null;
  source_timestamp: string | null;
  observed_at: string;
  stale_after_seconds: number;
  stale: boolean;
  current: boolean;
  evidence: string[];
  data: Record<string, any>;
  local_decision: IntegrationDecision | null;
  decision_options: string[];
};

export type IntegrationExecution = {
  id: string;
  application_id: string;
  application_name: string | null;
  action_id: string;
  parameters: Record<string, unknown>;
  status: string;
  risk: string;
  approval_required: boolean;
  approved_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  exit_code: number | null;
  output: string;
  error: string | null;
  result: Record<string, any>;
  artifact_ref: string | null;
  created_at: string;
};

export type InboxItem = {
  id: string;
  source_application: string;
  source_name: string;
  item_type: string;
  title: string;
  summary: string;
  project_id: string | null;
  project_name: string | null;
  priority: number;
  priority_label: string;
  evidence: string[];
  observed_at: string;
  state: string;
  actions: string[];
  target_path: string;
  resource_id: string | null;
  decision_state: string;
};

export type WorkflowEvent = {
  id: string;
  workflow_id: string;
  sequence: number;
  event_type: string;
  source: string;
  summary: string;
  payload: Record<string, any>;
  source_ref: string | null;
  created_at: string;
};

export type ExperimentWorkflow = {
  id: string;
  title: string;
  template: string;
  status: string;
  next_record_id: string | null;
  next_external_id: string;
  next_title: string;
  project_id: string | null;
  project_name: string | null;
  next_evidence: Record<string, any>;
  proposal: Record<string, any>;
  language_intention: Record<string, any>;
  repository_path: string;
  baseline_commit: string;
  approved_scope: string[];
  approval_hash: string | null;
  approved_at: string | null;
  approved_by: string | null;
  worker_request_id: string | null;
  worker_status: string | null;
  worker_result: Record<string, any>;
  patch: Record<string, any>;
  result_commit: string | null;
  measurement: Record<string, any>;
  review_execution_id: string | null;
  review_artifact_path: string | null;
  review_summary: Record<string, any>;
  adverse_review: boolean;
  final_decision: string | null;
  final_reason: string;
  override_adverse: boolean;
  failure: string | null;
  created_at: string;
  updated_at: string;
  events: WorkflowEvent[];
};

export type SearchResult = {
  id: string;
  source: string;
  source_id: string;
  title: string;
  subtitle: string;
  project_id: string | null;
  target_path: string;
  observed_at: string | null;
};

export type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    detail?: unknown;
  };
};
