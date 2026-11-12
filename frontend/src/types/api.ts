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
  pinned: boolean;
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
  scripts: {
    root: string;
    extensions: string[];
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

export type ResearchModelInfo = {
  id: string;
  label: string;
  local: boolean;
  configured: boolean;
  available: boolean;
};

export type ResearchModelCatalogue = {
  provider: string;
  route: string;
  configured: boolean;
  local: boolean;
  available: boolean;
  endpoint: string | null;
  selected: string | null;
  models: ResearchModelInfo[];
  detail: string;
  error: string | null;
};

export type ResearchContext = {
  schema: string;
  fingerprint: string;
  markdown: string;
  context: Record<string, any>;
};

export type ResearchChatMessage = {
  id: string;
  session_id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  status: "pending" | "completed" | "failed";
  error: string | null;
  provider: string | null;
  model: string | null;
  route: string | null;
  metadata: Record<string, any>;
  created_at: string;
};

export type ResearchChatSession = {
  id: string;
  application_id: string;
  resource_type: string;
  external_id: string;
  record_id: string | null;
  opportunity_title: string;
  context_schema: string;
  context_fingerprint: string;
  context_observed_at: string | null;
  model_route: string;
  model_id: string;
  model_local: boolean;
  provider: string;
  endpoint: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: ResearchChatMessage[];
  context_stale: boolean;
  current_fingerprint: string | null;
  freshness_notice: string | null;
};

export type ResearchChatSessionSummary = {
  id: string;
  opportunity_title: string;
  model_id: string;
  model_local: boolean;
  provider: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message: string | null;
  context_stale: boolean;
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

export type WriterDimension = {
  id: string;
  label: string;
  score: number | null;
  status_band: string;
  finding_codes: string[];
  raw_metrics: Record<string, any>;
  explanation?: string;
  limitations?: string[];
  scoring?: Record<string, any>;
};

export type WriterLocator = {
  chapter_id: string;
  source_path: string;
  relative_path: string;
  line_start: number | null;
  line_end: number | null;
  paragraph_index: number | null;
  section_title: string | null;
  excerpt: string;
};

export type WriterFinding = {
  finding_id: string | null;
  code: string;
  severity: "high" | "medium" | "low" | "info";
  dimension: string;
  subdimension: string;
  book_id: string;
  chapter_id: string | null;
  source_path: string | null;
  locator: WriterLocator | null;
  measured: Record<string, any>;
  reason: string;
  recommendation: string;
  limitations: string[];
};

export type WriterReadabilitySubdimension = {
  id: string;
  label: string;
  worst_score: number | null;
  worst_band: string;
  worst_chapter_id: string | null;
  chapters_flagged: number;
  chapter_scores: Array<Record<string, any>>;
};

export type WriterReadability = {
  note: string;
  subdimensions: WriterReadabilitySubdimension[];
  highest_risk: Record<string, any> | null;
};

export type WriterChapter = {
  chapter_id: string;
  title: string;
  source_path: string;
  relative_path: string;
  source_fingerprint: string;
  order: number;
  word_count: number;
  paragraph_count: number;
  sentence_count: number;
  status: string;
  current: boolean;
  status_band: string;
  highest_risk: Record<string, any> | null;
  dimensions: WriterDimension[];
  finding_codes: string[];
  finding_count: number;
  findings: WriterFinding[];
};

export type WriterBook = {
  project_id: string;
  title: string;
  status: string;
  profile: string;
  project_root: string;
  content_dir: string;
  repository_path: string;
  chapters_available: number;
  source_revision: string | null;
  source_dirty: boolean | null;
  report_id: string | null;
  scope: { kind: string; whole_book: boolean; chapter_ids: string[] } | null;
  last_checked: string | null;
  canonical_fingerprint: string | null;
  editing: Record<string, any>;
  pipeline: Record<string, any>;
  readability: WriterReadability | null;
  highest_risk: Record<string, any> | null;
  chapters: WriterChapter[];
  findings_preview: WriterFinding[];
  errors: string[];
  limitations: string[];
};

export type WriterDecision = {
  decision: string;
  scope: string;
  reason: string;
  created_at: string | null;
  decision_id: string | null;
};

export type WriterDecisionQueueItem = {
  id: string;
  project_id: string;
  book_title: string;
  book_status: string;
  stale: boolean;
  code: string;
  subdimension: string;
  severity: string;
  dimension: string;
  chapter_id: string;
  chapter_title: string;
  chapter_order: number;
  chapter_name: string;
  finding_id: string;
  reason: string;
  recommendation: string;
  locator: WriterLocator | null;
  measured: Record<string, any>;
  limitations: string[];
  count: number;
  chapter_count: number;
  decided_count: number;
  undecided_count: number;
  state: "undecided" | "partial" | "decided" | "stale";
  decision: WriterDecision | null;
  workbench_link: string;
  workbench_book_ready: boolean;
};

export type WriterDecisionTotals = {
  groups: number;
  findings: number;
  undecided: number;
  decided: number;
  stale_groups: number;
  missing_identity: number;
  confirmed: number;
  dismissed: number;
  deferred: number;
};

export type WriterCampaignChapter = {
  chapter_id: string;
  status: string;
  outcomes: Record<string, number>;
  candidates_made: number;
  model_calls: number;
  report_id: string | null;
};

export type WriterBookCampaign = {
  campaign_id: string;
  mode: string;
  state: string;
};

export type CampaignActiveRun = {
  run_id: string;
  campaign_id: string;
  state: string;
  stop_reason: string;
};

export type WriterCampaignBook = {
  book_id: string;
  campaign_root: string;
  totals: Record<string, number>;
  campaigns: WriterBookCampaign[];
  chapters: WriterCampaignChapter[];
  active_runs: CampaignActiveRun[];
};

export type WriterStrategyCard = {
  strategy: string;
  evaluated: number;
  supported: number;
  support_rate: number | null;
  evidence_level: string;
  book_id?: string;
  denominator?: string;
};

export type WriterModelCard = {
  model: string;
  role: string;
  attempts: number;
  evaluated: number;
  supported: number;
  evidence_level: string;
  denominator?: string;
};

export type WriterFailureFamily = {
  family: string;
  attempts: number;
  sample_limitation?: string;
};

export type WriterOversizedRegion = {
  chapter_id: string;
  opportunity_id: string;
  reason: string;
  plan_id: string;
};

export type WriterStrategyVersion = {
  strategy_id: string;
  version: string;
  status: string;
  content_hash?: string;
  book_id?: string;
};

export type WriterExperiment = {
  experiment_id: string;
  status: string;
  baseline_version?: string;
  candidate_version?: string;
  book_id?: string;
};

export type WriterEvolutionDecision = {
  decision_id: string;
  decision: string;
  actor?: string;
  experiment_id?: string;
  book_id?: string;
};

export type WriterEvolutionSummary = {
  available: boolean;
  detail: string;
  error: string | null;
  totals: Record<string, number>;
  versions: WriterStrategyVersion[];
  proposals: Array<Record<string, any>>;
  experiments: WriterExperiment[];
  decisions: WriterEvolutionDecision[];
  books: Array<{ book_id: string; versions: number }>;
  limitations: string[];
  unreadable_files: number;
};

export type WriterIntelSummary = {
  available: boolean;
  detail: string;
  error: string | null;
  totals: Record<string, number>;
  strategies: WriterStrategyCard[];
  models: WriterModelCard[];
  failures: WriterFailureFamily[];
  oversized: WriterOversizedRegion[];
  books: Array<{ book_id: string; attempts: number; oversized: number }>;
  limitations: string[];
  unreadable_files: number;
};

export type WriterCampaignSummary = {
  available: boolean;
  detail: string;
  error: string | null;
  totals: Record<string, number>;
  books: WriterCampaignBook[];
  limitations: string[];
  unreadable_files: number;
};

export type WriterWorkspace = {
  available: boolean;
  detail: string;
  error: string | null;
  last_checked_at: string | null;
  generated_at: string | null;
  totals: Record<string, number>;
  review_queue: Array<Record<string, any>>;
  decision_queue: WriterDecisionQueueItem[];
  decision_totals: WriterDecisionTotals;
  workbench: {
    url: string;
    book: string | null;
    ready: boolean;
    note: string;
  };
  books: WriterBook[];
  limitations: string[];
  campaigns?: WriterCampaignSummary;
  intel?: WriterIntelSummary;
  strategy_evolution?: WriterEvolutionSummary;
};

export type QualityDimension = {
  dimension: string;
  score: number;
  evidence: string;
  evidence_validated: boolean;
};

export type QualityEvaluation = {
  id: string;
  project_id: string | null;
  book_id: string;
  chapter_id: string;
  source_path: string;
  chapter_revision: string;
  rubric_id: string;
  rubric_version: number;
  prompt_version: string;
  requested_model: string | null;
  actual_model: string | null;
  status: string;
  derived_state: string;
  overall: number | null;
  aggregation_method: string;
  dimensions: Record<string, QualityDimension>;
  findings: Array<Record<string, any>>;
  uncertainty: string;
  limitations: string[];
  execution: Record<string, any>;
  previous_evaluation_id: string | null;
  supersedes: string | null;
  workbench_url: string | null;
  workbench_link: string | null;
  section_id: string | null;
  section_title: string | null;
  char_span: Array<any>;
  section_sha: string | null;
  campaign_id: string | null;
  strategy: string;
  created_at: string;
};

export type QualityReview = {
  id: string;
  evaluation_id: string | null;
  finding_id: string;
  decision: string;
  reason: string;
  reviewer: string;
  source_digest: string;
  source_status: string;
  created_at: string;
};

export type TechnicalClaim = {
  id: string;
  project_id: string | null;
  book_id: string;
  chapter_id: string;
  source_path: string;
  source_revision: string;
  source_start_line: number | null;
  source_end_line: number | null;
  source_excerpt: string;
  claim_text: string;
  normalized_assertion: string;
  claim_type: string;
  epistemic_role: string;
  assumptions: string[];
  qualifications: string[];
  extraction_method: string;
  model_id: string | null;
  prompt_version: string;
  extraction_status: string;
  quote_validated: boolean;
  campaign_id: string | null;
  derived_state: string;
  created_at: string;
};

export type TechnicalEvidence = {
  id: string;
  claim_id: string;
  evidence_type: string;
  source_location: string;
  source_revision: string;
  source_span: string;
  evidence_excerpt: string;
  discovery_method: string;
  verification_method: string;
  verification_status: string;
  limitations: string;
  created_at: string;
};

export type TechnicalVerification = {
  id: string;
  claim_id: string;
  evidence_id: string | null;
  method: string;
  status: string;
  detail: string;
  spec_id: string;
  spec_version: number;
  model_id: string | null;
  prompt_version: string;
  prompt_hash: string | null;
  token_usage: string;
  input_tokens: number | null;
  output_tokens: number | null;
  campaign_id: string | null;
  created_at: string;
};

export type TechnicalChapterAssessment = {
  chapter_id: string;
  title: string | null;
  source_revision: string;
  claims_total: number;
  claims_source_verified: number;
  claims_unresolved: number;
  by_status: Record<string, number>;
  by_method: Record<string, number>;
  claims: TechnicalClaim[];
};

export type TechnicalCompleteness = {
  chapter_id: string;
  live_revision: string | null;
  regions_total: number;
  regions_processed: number;
  regions_capped: number;
  regions_failed: number;
  regions_not_started: number;
  regions_stale: number;
  claims_total: number;
  claims_source_verified: number;
  claims_stale: number;
  requirements_total: number;
  by_satisfaction: Record<string, number>;
  by_applicability: Record<string, number>;
  open_gaps: number;
  gap_types: string[];
  assessment: string;
};

export type TechnicalRequirement = {
  id: string;
  requirement_key: string;
  label: string;
  requirement_type: string;
  acceptance_rule: string;
  rationale: string;
  applicability: string;
  satisfaction: string;
  satisfaction_detail: string;
  waived_reason: string;
};

export type TechnicalGap = {
  id: string;
  chapter_id: string;
  claim_id: string | null;
  requirement_id: string | null;
  gap_type: string;
  title: string;
  detail: string;
  searched_scope: string;
  status: string;
  priority_rationale: string;
  created_at: string;
};

export type TechnicalObjective = {
  id: string;
  chapter_id: string;
  statement: string;
  source: string;
  status: string;
  created_at: string;
};

export type QualityChapter = {
  chapter_id: string;
  chapter_title: string | null;
  evaluations: QualityEvaluation[];
  sections: QualityEvaluation[];
  current: QualityEvaluation | null;
};

export type QualityWorkspace = {
  project_id: string;
  book_id: string;
  chapters_total: number;
  chapters_evaluated: number;
  chapters_current: number;
  chapters: QualityChapter[];
  limitations: string[];
};

export type QualityDiscovery = {
  chapter_id: string;
  title: string | null;
  source_path: string;
  revision: string;
  has_current: boolean;
  current_model: string | null;
  current_id: string | null;
  compatible: boolean;
  eligibility: string;
};

export type QualityCampaign = {
  id: string;
  project_id: string | null;
  book_id: string;
  book_root: string;
  mode: string;
  chapter_selection: string[];
  fingerprints: Record<string, string>;
  rubric_id: string;
  rubric_version: number;
  prompt_version: string;
  model: string | null;
  strategy: string;
  assessment_type: string;
  status: string;
  total: number;
  completed: number;
  skipped: number;
  failed: number;
  remaining: number;
  usage: Record<string, any>;
  costs_unknown: boolean;
  current_chapter: string | null;
  error: string | null;
  heartbeat_at: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export type ArtifactLoadObservation = {
  id: string;
  project_id: string | null;
  book_id: string;
  chapter_id: string;
  source_path: string;
  chapter_revision: string;
  aggregation_version: string;
  detector_version: string;
  status: string;
  derived_state: string;
  assessment_state: string;
  assessment_policy: string;
  eligible_words: number;
  evaluated_units: number;
  total_candidates: number;
  confirmed: number;
  high: number;
  medium: number;
  low: number;
  unreviewed: number;
  invalid_evidence: number;
  affected_regions: number;
  findings_per_1k: number | null;
  findings_per_100_units: number | null;
  region_rate: number | null;
  coverage_mechanical: number;
  coverage_semantic: number;
  weighted_load: number | null;
  mechanical_pressure: number | null;
  baseline_eligible_words: number;
  revised_eligible_words: number;
  findings: Array<Record<string, any>>;
  regions: Array<Record<string, any>>;
  limitations: string[];
  execution: Record<string, any>;
  previous_observation_id: string | null;
  supersedes: string | null;
  workbench_url: string | null;
  workbench_link: string | null;
  compatible_basis: string;
  created_at: string;
};

export type ArtifactLoadChapter = {
  chapter_id: string;
  observations: ArtifactLoadObservation[];
  current: ArtifactLoadObservation | null;
};

export type ArtifactLoadWorkspace = {
  project_id: string;
  book_id: string;
  chapters_total: number;
  chapters_observed: number;
  chapters_current: number;
  chapters: ArtifactLoadChapter[];
  limitations: string[];
};

export type LanguageObservation = {
  id: string;
  workflow_id: string;
  schema: string;
  template: string;
  intention_ref: string;
  subject: string;
  properties: Array<{
    id: string;
    expected: unknown;
    observed: unknown;
    difference: unknown;
    within_constraint: boolean;
  }>;
  measurement_method: string | null;
  evidence: string[];
  provenance: Record<string, any>;
  uncertainty: string[];
  constraint_result: string;
  evaluation_version: string;
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
  cancel_requested: boolean;
  cancelled_at: string | null;
  failure: string | null;
  created_at: string;
  updated_at: string;
  events: WorkflowEvent[];
  language_observations: LanguageObservation[];
};

export type ProjectEvidenceTimeline = {
  project_id: string;
  workflows: ExperimentWorkflow[];
  observations: LanguageObservation[];
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

export type GitActivityRoot = {
  path: string;
  name: string;
  category: string;
  enabled: boolean;
  git_enabled: boolean;
  added_at: string | null;
  last_git_sync_at: string | null;
  last_git_error: string | null;
};

export type GitRepo = {
  id: string;
  root_path: string;
  path: string;
  name: string;
  branch: string | null;
  head_sha: string | null;
  accessible: boolean;
  is_bare: boolean;
  is_shallow: boolean;
  last_indexed_at: string | null;
  backfill_complete: boolean;
  total_commits: number;
  has_agents: boolean;
  has_description: boolean;
  context_status: string;
  error: string | null;
};

export type GitCommit = {
  repo_id: string;
  repo_name: string;
  repo_path: string;
  root_path: string;
  sha: string;
  short_sha: string;
  subject: string;
  author_name: string;
  author_email: string;
  author_ts: number;
  committer_ts: number;
  committer_tz: string;
  parents: string[];
  branches: string[];
  files_changed: number;
  insertions: number;
  deletions: number;
  is_merge: boolean;
  is_root: boolean;
  reachable: boolean;
  review_count: number;
  review_status: string;
};

export type GitTimeline = {
  items: GitCommit[];
  total: number;
  partial: boolean;
  limit: number;
  offset: number;
};

export type GitSummary = {
  commits_today: number;
  projects_today: number;
  commits_week: number;
  commits_reviewed: number;
  commits_indexed: number;
  repos_indexed: number;
  backfill_pending: number;
  complete: boolean;
  generated_at: string;
};

export type GitReview = {
  id: string;
  repo_id: string;
  review_type: string;
  commit_sha: string | null;
  base_sha: string | null;
  target_sha: string | null;
  commit_shas: string[];
  reviewer_type: string;
  requested_model: string;
  observed_model: string | null;
  model_route: string;
  profile: string;
  status: string;
  verdict: string | null;
  findings: Array<Record<string, any>>;
  summary: string;
  tests: Record<string, any>;
  architecture: Record<string, any>;
  limitations: string[];
  prompt_hash: string;
  diff_hash: string;
  context_fingerprint: string;
  evidence_coverage: Record<string, any>;
  usage_info: Record<string, any>;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  feedback: Array<{ id: string; rating: string; detail: string; created_at: string }>;
};

export type GitScanStatus = {
  scan_id: string | null;
  status: string;
  running: boolean;
  repos_discovered?: number;
  repos_indexed?: number;
  commits_new?: number;
  backfill_pending?: number;
  total_repos?: number;
  total_commits?: number;
  errors?: Array<{ path: string; error: string }>;
  error?: string | null;
};

export type ReviewModelCatalogue = {
  provider: string;
  route: string;
  configured: boolean;
  local: boolean;
  available: boolean;
  endpoint: string | null;
  selected: string | null;
  models: Array<{ id: string; label: string; local: boolean; configured: boolean; available: boolean }>;
  detail: string;
  error: string | null;
};

export type GitDailyProject = {
  repo_id: string;
  repo_name: string;
  date: string;
  timezone: string;
  start_ts: number;
  end_ts: number;
  commit_count: number;
  insertions: number;
  deletions: number;
  files_changed: number;
  files_changed_distinct: number | null;
  files_changed_estimated: boolean;
  first_ts: number;
  last_ts: number;
  backfill_complete: boolean;
  index_complete: boolean;
  coverage_warning: string | null;
  snapshot_fingerprint: string;
  commit_shas: string[];
  review_status: string;
  review_id: string | null;
  review_mode: string | null;
  review_verdict: string | null;
  review_completed_at: string | null;
  review_stale: boolean;
  review_count: number;
};

export type GitDailyProjects = {
  date: string;
  timezone: string;
  start_ts: number;
  end_ts: number;
  total_commits: number;
  total_repos: number;
  projects: GitDailyProject[];
  partial: boolean;
  backfill_pending: number;
};

export type GitDailyPrompt = {
  markdown: string;
  prompt_hash: string;
  diff_hash: string;
  context_fingerprint: string;
  size_chars: number;
  truncated: boolean;
  redactions: string[];
  redaction_count: number;
  coverage: Record<string, unknown>;
  commit_shas: string[];
  snapshot_fingerprint: string;
  date: string;
  timezone: string;
  mode: string;
  profile: string;
  start_ts: number;
  end_ts: number;
};

export type CultivationStageDef = {
  id: string;
  label: string;
  color: string;
};

export type CultivationProgress = {
  current: number | null;
  target: number;
  unit: string;
  percent: number | null;
  unknown_reason: string | null;
  achieved: boolean;
  estimate_label: string | null;
  item_count: number;
  pipeline: Record<string, number>;
  milestones_reached: number[];
  next_milestone: number | null;
  live_observed: number | null;
  live_sync_at: string | null;
  live_stale: boolean;
  disagreement: string | null;
};

export type CultivationGoal = {
  id: string;
  name: string;
  description: string;
  category: string;
  unit: string;
  target_value: number;
  measurement_type: string;
  baseline_value: number | null;
  baseline_note: string;
  baseline_provenance: string;
  qualifying_stage: string;
  window_days: number | null;
  recurring_mode: string;
  priority: number;
  state: string;
  pinned: boolean;
  pin_order: number;
  privacy: string;
  completion_criteria: string;
  milestones: number[];
  dependencies: string[];
  evidence_source: string;
  skill_id: string | null;
  skill_name: string | null;
  created_at: string;
  updated_at: string;
  progress: CultivationProgress;
};

export type CultivationMembership = {
  item_id: string;
  goal_id: string;
  goal_name: string | null;
  stage: string;
  evidence_status: string;
  quality_evidence: Record<string, any>;
  qualified: boolean;
  qualified_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CultivationItem = {
  id: string;
  title: string;
  item_type: string;
  notes: string;
  tags: string[];
  provenance: string;
  source_application: string | null;
  source_project_id: string | null;
  source_project_name: string | null;
  source_ref: string | null;
  created_at: string;
  updated_at: string;
  memberships: CultivationMembership[];
};

export type CultivationMeasurement = {
  id: string;
  goal_id: string;
  value: number;
  observed_at: string;
  note: string;
  source: string;
  created_at: string;
};

export type CultivationEvent = {
  id: string;
  goal_id: string | null;
  item_id: string | null;
  item_title: string | null;
  event_type: string;
  from_value: string | null;
  to_value: string | null;
  note: string;
  evidence_ref: string | null;
  occurred_at: string | null;
  created_at: string;
};

export type CultivationEvidence = {
  id: string;
  goal_id: string | null;
  item_id: string | null;
  kind: string;
  reference: string;
  note: string;
  verified: boolean;
  created_at: string;
};

export type CultivationRank = {
  id: string;
  name: string;
  concept: string;
  qualified: boolean;
  requires: Record<string, any>;
};

export type CultivationHudGoal = {
  id: string;
  name: string;
  unit: string;
  state: string;
  privacy: string;
  progress: CultivationProgress;
};

export type CultivationHud = {
  primary: CultivationHudGoal | null;
  pinned: CultivationHudGoal[];
  rank: CultivationRank | null;
  recent_completions: CultivationEvent[];
  generated_at: string;
  cycle: CultivationCycle | null;
  pinned_skills: CultivationSkill[];
};

export type CultivationSkillGoal = {
  id: string;
  name: string;
  unit: string;
  state: string;
  progress: CultivationProgress;
};

export type CultivationSkill = {
  id: string;
  name: string;
  icon: string;
  category: string;
  description: string;
  pinned: boolean;
  pin_order: number;
  state: string;
  created_at: string;
  updated_at: string;
  goals_total: number;
  goals_achieved: number;
  item_completions: number;
  goals: CultivationSkillGoal[];
};

export type CultivationSource = {
  id: string;
  name: string;
  kind: string;
  skill_id: string | null;
  goal_id: string | null;
  path: string;
  config: Record<string, any>;
  last_sync_at: string | null;
  last_status: string;
  last_error: string | null;
  fingerprint: string;
  observed: Record<string, any>;
  created_at: string;
  updated_at: string;
};

export type CultivationCycleDay = {
  day: number | null;
  mode: string;
  length_days: number;
  past_length: boolean;
  label: string;
};

export type CultivationCycle = {
  id: string;
  number: number;
  name: string;
  length_days: number;
  start_date: string | null;
  snapshot_day: number | null;
  snapshot_note: string;
  state: string;
  notes: string;
  created_at: string;
  updated_at: string;
  day: CultivationCycleDay;
  focus_goal_ids: string[];
  progress: {
    window: { from: string; to: string } | null;
    focus: Array<{ goal_id: string; goal_name: string; completions_in_window: number | null; started_in_window: number | null; current: number | null }>;
  };
};

export type CultivationRepoState = {
  repo_id: string;
  repo_uid: string;
  name: string;
  path: string | null;
  root_path: string | null;
  branch: string | null;
  head_sha: string | null;
  accessible: boolean;
  indexed: boolean;
  total_commits: number;
  first_commit_ts: number | null;
  last_commit_ts: number | null;
  backfill_complete: boolean;
  last_indexed_at: string | null;
  has_agents: boolean;
  has_description: boolean;
  context_status: string;
  projects: Array<{ id: string; name: string }>;
  qualification: string;
  lifecycle_stage: string | null;
  classification: string;
  rationale: string;
  evidence: Record<string, any>;
  decided_by: string;
  decided_at: string | null;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
  origin?: string;
  url?: string | null;
  description?: string | null;
  visibility?: string | null;
  language?: string | null;
  private?: boolean;
  fork?: boolean;
  pushed_at?: string | null;
  missing?: boolean;
};

export type CultivationApp = {
  id: string;
  name: string;
  description: string;
  lifecycle_stage: string;
  release_evidence: Record<string, any>;
  completed_at: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
  repos: Array<{ repo_id: string; name: string; path: string | null; qualification: string; accessible: boolean }>;
  memberships: Array<{ goal_id: string; goal_name: string | null; stage: string; completed_at: string | null; qualified: boolean; evidence_status: string }>;
};

export type CultivationConfig = {
  stages: CultivationStageDef[];
  ranks: Array<{ id: string; name: string; concept: string; requires: Record<string, any> }>;
};

export type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    detail?: unknown;
  };
};

export type ScriptRecord = {
  id: string;
  library_key: string;
  current_relpath: string;
  original_relpath: string;
  script_number: number | null;
  title: string;
  content_sha256: string;
  file_size: number;
  mtime_ns: number;
  status: string;
  archived: boolean;
  missing: boolean;
  discovered_at: string;
  last_seen_at: string | null;
  completed_at: string | null;
  review_status: string;
  last_review_at: string | null;
  legacy_item_id: string | null;
  created_at: string;
  updated_at: string;
  duplicate_number_group: string[] | null;
  duplicate_content_group: string[] | null;
  events: Array<{
    id: string;
    event_type: string;
    from_value: string | null;
    to_value: string | null;
    note: string;
    created_at: string;
  }>;
  links: Array<{
    source_id: string;
    target_id: string;
    kind: string;
    confirmed: boolean;
    note: string;
    evidence?: string;
    confidence?: string;
    updated_at?: string;
  }>;
  usage_count: number;
  personal_rating: number | null;
  personal_target: string;
  personal_effect: string;
  last_used_at: string | null;
  latest_review: {
    id: string;
    created_at: string;
    freshness: string;
    purpose: string;
    readiness: string;
    model: string;
  } | null;
};

export type ScriptContent = {
  id: string;
  relpath: string;
  title: string;
  content: string;
  truncated: boolean;
  content_sha256: string;
  stored_sha256: string;
  matches_stored: boolean;
};

export type ScriptStatus = {
  root: string;
  library_key: string;
  configured: boolean;
  exists: boolean;
  is_dir: boolean;
  readable: boolean;
  writable: boolean;
  status: string;
  last_sync_at: string | null;
  last_error: string | null;
  fingerprint: string;
  observed: Record<string, unknown>;
  counts: {
    total: number;
    by_status: Record<string, number>;
    completed: number;
    ready?: number;
    needs_review?: number;
    present?: number;
    archived: number;
    missing: number;
  };
  duplicate_numbers: Record<string, string[]>;
  duplicate_content: Record<string, string[]>;
  extensions: string[];
  week: { week_start: string; week_end: string; week_start_date: string; week_end_date: string; label: string; timezone: string };
  libraries: string[];
};

export type ScriptRelationship = {
  source_id: string;
  target_id: string;
  kind: string;
  confirmed: boolean;
  note: string;
  evidence: string;
  confidence: string;
  updated_at?: string;
  created_at?: string;
};

export type ScriptWork = {
  work_id: string;
  root_id: string;
  member_ids: string[];
  members: Array<{
    id: string;
    relpath: string;
    number: number | null;
    status: string;
    completed_at: string | null;
    archived: boolean;
  }>;
  canonical_id: string;
  canonical_number: number | null;
  size: number;
  work_number: number;
};

export type ScriptMigrationItem = {
  id: string;
  current: string;
  proposed: string;
  current_number: number | null;
  proposed_number: number;
  sha256: string;
  status: string;
  archived: boolean;
  completed_at: string | null;
  work_hint: { kinds: string[]; confirmed: boolean } | null;
};

export type ScriptMigration = {
  id: string;
  library_key: string;
  status: string;
  manifest_hash: string;
  approved_at: string | null;
  applied_at: string | null;
  rolled_back_at: string | null;
  error: string | null;
  report: Record<string, unknown>;
  item_count: number;
  created_at: string;
  updated_at: string;
};

export type ScriptReview = {
  id: string;
  script_id: string;
  content_sha256: string;
  model: string;
  route: string;
  provider: string;
  assessment: Record<string, unknown>;
  review_schema: string;
  freshness: string;
  latency_ms: number;
  created_at: string;
};

export type ScriptBatchItem = {
  script_id: string;
  relpath: string | null;
  title: string | null;
  status: string;
  review_id: string | null;
  reused: boolean;
  attempts: number;
  error: string | null;
};

export type ScriptBatch = {
  id: string;
  library_key: string;
  status: string;
  model: string;
  rubric_version: string;
  schema_version: string;
  selection: Record<string, unknown>;
  counts: { total: number; pending: number; reviewed: number; failed: number; skipped: number; reused: number };
  error: string | null;
  items: ScriptBatchItem[];
  created_at: string;
  updated_at: string;
};

export type LibrarySynthesis = {
  id: string;
  library_key: string;
  kind: string;
  status: string;
  manifest: Record<string, unknown>;
  manifest_hash: string;
  report: Record<string, unknown>;
  error: string | null;
  freshness: string;
  created_at: string;
};

export type ScriptCandidate = {
  id: string;
  library_key: string;
  title: string;
  version: string;
  kind: string;
  status: string;
  content: string;
  word_count: number;
  est_seconds: number;
  validation: Record<string, unknown>;
  critique: Record<string, unknown>;
  source_manifest: Record<string, unknown>;
  provenance: Record<string, unknown>;
  parent_candidate_id: string | null;
  promoted_script_id: string | null;
  promoted_relpath: string | null;
  created_at: string;
  updated_at: string;
};

export type IntelligenceCoverage = {
  total: number;
  current: number;
  stale: number;
  never: number;
  by_script: Record<string, string>;
  durations: { samples: number; median_seconds: number | null; min_seconds: number | null; max_seconds: number | null };
  completed: number;
};

export type EnsureOpenResult = {
  url: string;
  application_id: string;
  state: string;
  ownership: string;
  process_id: string | null;
  detail: string | null;
};
