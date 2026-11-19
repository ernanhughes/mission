export type LivingBookState =
  | "ready"
  | "needs_source"
  | "model_unavailable"
  | "not_connected"
  | "unavailable"
  | "error"
  | "not_found"
  | "not_a_book"
  | "no_manuscript";

export type LivingBookCandidate = {
  kind: "manuscript" | "repository";
  path: string;
  manuscript_root: string;
  available: boolean;
  recommended: boolean;
  detail: string;
  files?: number;
  bytes?: number;
  reason?: string;
  role?: string;
};

export type LivingBookQualityCoverage = {
  status: string;
  current?: number;
  total?: number;
  rubric?: string;
  detail?: string;
  claims_total?: number;
};

export type LivingBookQualityMeasure = {
  id: string;
  kind: string;
  scope: string;
  chapter_id?: string | null;
  status: string;
  label: string;
  detail?: string;
  rubric?: string;
  rubric_version?: number;
  model?: string | null;
  observed_at?: string | null;
  chapter_revision?: string | null;
  value?: Record<string, any>;
  findings?: Array<Record<string, any>>;
  limitations: string[];
};

export type LivingBookQuality = {
  schema: string;
  generated_at?: string;
  book?: Record<string, any>;
  chapter?: Record<string, any> | null;
  coverage: Record<string, LivingBookQualityCoverage>;
  measures: LivingBookQualityMeasure[];
  summary: {
    rubric?: string;
    chapters_total?: number;
    chapters_current?: number;
    chapters_evaluated?: number;
    overall_min?: number | null;
    overall_max?: number | null;
    dimension_means?: Record<string, number>;
    weakest_chapters?: Array<Record<string, any>>;
    limitations?: string[];
  };
  limitations: string[];
};

export type LivingBookQualitySummary = {
  schema: string;
  coverage: Record<string, LivingBookQualityCoverage>;
  summary: LivingBookQuality["summary"];
  limitations: string[];
};

export type LivingBookChapter = {
  chapter_id: string;
  path: string;
  title: string;
  order: number;
  word_count: number;
  sha256: string;
  status: "current" | "changed" | string;
};

export type LivingBookReading = {
  chapter_id: string;
  chapter_sha256: string;
  progress: number;
  anchor: string;
  updated_at: string;
};

export type LivingBookAnnotation = {
  id: string;
  chapter_id: string;
  chapter_sha256: string;
  quote: string;
  note: string;
  start: number | null;
  end: number | null;
  created_at: string;
  stale?: boolean;
};

export type LivingBookNote = {
  id: string;
  chapter_id: string;
  chapter_sha256: string;
  markdown: string;
  citations?: Array<Record<string, any>>;
  conversation_id?: string | null;
  model?: string | null;
  generated_at: string;
  status: string;
};

export type LivingBookDetails = {
  id: string;
  title: string;
  label: string;
  workspace_id: string;
  source_root: string;
  manuscript_root: string;
  manuscript_relative: string;
  ready: boolean;
  error: string | null;
  source: Record<string, any>;
  chapters: LivingBookChapter[];
  chapter_count: number;
  reading: LivingBookReading | null;
  annotations: LivingBookAnnotation[];
  notes: LivingBookNote[];
  conversations: Array<Record<string, any>>;
  model: { name: string; transport: string; ready: boolean };
  limitations: string[];
};

export type LivingBookStatus = {
  project_id: string;
  project_name: string;
  book_title: string;
  manuscript_root: string;
  available: boolean;
  state: LivingBookState;
  detail: string;
  alive_url?: string;
  quality: LivingBookQualitySummary;
  candidates: LivingBookCandidate[];
  book: LivingBookDetails | null;
};

export type LivingBookChapterContent = {
  chapter_id: string;
  path: string;
  title: string;
  order: number;
  sha256: string;
  word_count: number;
  markdown: string;
  front_matter: Record<string, string>;
  sections: Array<{ level: number; title: string; line: number }>;
  figures: Array<{ kind: string; src: string; alt: string; caption: string }>;
  status: string;
};

export type LivingBookCitation = {
  document_id?: string;
  source_ref?: string;
  quote?: string;
  line_start?: number;
  line_end?: number;
};

export type LivingBookMessage = {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  status?: string | null;
  created_at?: string | null;
  citations?: LivingBookCitation[];
  actions?: Array<Record<string, any>>;
  verification?: Record<string, any> | null;
  evaluation?: Record<string, any> | null;
  reply_status?: string | null;
  in_model_scope?: boolean | null;
};

export type LivingBookSession = {
  id: string;
  state: string;
  max_calls?: number;
  max_tokens?: number;
  expires_at?: string;
  usage?: { calls?: number; tokens?: number };
};

export type LivingBookConversation = {
  id: string;
  title?: string;
  workspace_id?: string;
  updated_at?: string;
  messages: LivingBookMessage[];
  calls?: Array<Record<string, any>>;
  answer?: string;
  citations?: LivingBookCitation[];
  actions?: Array<Record<string, any>>;
  verification?: Record<string, any> | null;
  status?: string;
  session?: LivingBookSession | null;
  mode?: string;
  chapter_id?: string | null;
  quality_used?: boolean;
};

export type LivingBookImprovementBlocker = {
  code: string;
  detail: string;
};

export type LivingBookImprovementEvidence = {
  ref: string;
  kind: string;
  status: string;
  measure_id: string;
  rubric?: string | null;
  observed_at?: string | null;
  chapter_revision?: string | null;
  quote?: string;
  quote_validated?: boolean;
  value?: { overall?: number | null; economy?: number | null };
  limitations?: string[];
};

export type LivingBookImprovementPlan = {
  mode: string;
  workflow_version: number;
  workflow_definition_id?: string | null;
  workflow_definition_sha256?: string | null;
  workflow_binding_sha256?: string | null;
  model_calls: number;
  output_tokens: number;
  wall_seconds: number;
  characters?: number;
  section_count?: number;
  plan_sha256: string;
  governor?: Record<string, any> | null;
};

export type LivingBookImprovementPreview = {
  schema: string;
  generated_at: string;
  eligible: boolean;
  blockers: LivingBookImprovementBlocker[];
  warnings: string[];
  focus: string;
  project_id: string;
  book_id: string;
  workspace_id: string;
  chapter: {
    chapter_id: string;
    path: string;
    title: string;
    sha256: string;
    word_count?: number;
    status: string;
  };
  source: Record<string, any>;
  model: { name: string; transport: string; ready: boolean };
  quality: Record<string, any>;
  evidence: LivingBookImprovementEvidence | null;
  excluded: Array<{
    ref: string;
    label: string;
    status: string;
    reason: string;
  }>;
  brief: string;
  criteria_sha256?: string | null;
  intent: Record<string, any>;
  intent_sha256: string;
  plan: LivingBookImprovementPlan | null;
  experience: Record<string, any>;
  recent_improvements?: Array<{
    run_id: string;
    improvement_id?: string;
    chapter_path?: string;
    decision?: string;
    evaluation_status?: string;
    verdict?: string | null;
    created_at?: string;
    source_version?: { status?: string };
  }>;
  authority: Record<string, string>;
  notice: string;
  use_experience: boolean;
};

export type LivingBookImprovementRun = {
  schema: string;
  book_id: string;
  workspace_id: string;
  run_id: string;
  status: string;
  terminal: boolean;
  status_label: string;
  reason?: string | null;
  workflow?: Record<string, any> | null;
  budget?: Record<string, any> | null;
  usage?: { calls?: number; tokens?: number } | null;
  stages: Array<{
    stage_id: string;
    state: string;
    error_category?: string | null;
    model_invocation_id?: string | null;
    pi_run_id?: string | null;
  }>;
  chapter_path?: string | null;
  provenance: string;
  missing: string[];
  original: { path?: string | null; sha256?: string | null };
  proposal?: {
    artifact_id: string;
    artifact_sha256: string;
    sha256: string;
    markdown: string;
    rationale?: string | null;
    coverage?: string | null;
    limitations?: string | null;
  } | null;
  change?: {
    differs: boolean;
    lines_added: number;
    lines_removed: number;
    blocks: Array<{ op: string; lines: string[] }>;
    unified: string[];
    truncated: boolean;
  } | null;
  evaluation?: {
    status: string;
    kind?: string;
    verdict?: string;
    assessment?: string;
    limitations?: string;
    model?: string | null;
    note?: string;
  } | null;
  source_version?: { status: string; reason?: string } | null;
  state: { decision: string; decided_at?: string | null; event_id?: string };
  history: Array<Record<string, any>>;
  experience?: Record<string, any> | null;
  plan?: Record<string, any> | null;
  notice: string;
  applied: boolean;
};
