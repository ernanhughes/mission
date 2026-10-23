import type {
  ActivityEvent,
  Adapter,
  Application,
  Book,
  Dashboard,
  Project,
  ProjectDetail,
  Settings,
  Task,
} from "../types/api";

const now = "2026-10-23T12:00:00+00:00";

export function makeApplication(overrides: Partial<Application> = {}): Application {
  return {
    id: "next",
    name: "Next",
    description: "Research discovery and evidence.",
    category: "research",
    icon: "N",
    tags: ["research"],
    enabled: true,
    archived: false,
    pinned: true,
    display_order: 10,
    repository_path: "C:\\Projects\\next",
    additional_paths: [],
    working_directory: null,
    documentation_paths: [],
    output_paths: [],
    integration_adapter: "next",
    adapter_enabled: true,
    adapter_config: {},
    related_projects: ["math"],
    related_books: [],
    outcomes: ["books"],
    dependencies: [],
    control_policy: { allow_launch: true, confirmation_required: false },
    source: "default",
    notes: "",
    launch_definitions: [
      {
        id: "next-run",
        application_id: "next",
        name: "Next run",
        launch_type: "command",
        executable: "python.exe",
        arguments: ["-m", "next"],
        working_directory: "C:\\Projects\\next",
        env_names: [],
        browser_url: null,
        health_type: "none",
        health_url: null,
        expected_port: null,
        is_primary: true,
        enabled: true,
        verified: true,
        verification_note: "Fixture",
        shutdown_behavior: "terminate",
      },
    ],
    status: {
      state: "stopped",
      label: "Stopped",
      detail: "A launch action is configured but no managed process is running.",
      ownership: "none",
      observed_at: null,
      stale: false,
      health_state: null,
      process_id: null,
    },
    actions: {
      launch: { enabled: true, reason: null },
      stop: { enabled: false, reason: "No Mission Control-owned process is running." },
      restart: { enabled: true, reason: null },
      open_repository: { enabled: false, reason: "Configure an editor command in Settings." },
      open_documentation: { enabled: false, reason: "No existing documentation path is configured." },
      open_url: { enabled: false, reason: "No browser URL is configured." },
      logs: { enabled: false, reason: "No process log is available yet." },
      check_health: { enabled: false, reason: "No enabled health check is configured." },
    },
    last_launch_success_at: null,
    last_launch_failure_at: null,
    last_failure_detail: null,
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

export function makeBook(overrides: Partial<Book> = {}): Book {
  return {
    id: "book-language",
    project_id: "language",
    project_name: "Language",
    title: "Language: When Intelligence Enters the Channel",
    status: "editorial_review",
    current_milestone: "Author review of five editorial checkpoints.",
    next_action: "Read the five author-review checkpoints.",
    manuscript_paths: ["C:\\Projects\\language\\content\\books\\language"],
    implementation_paths: ["C:\\Projects\\project-language"],
    published_url: null,
    local_url: null,
    quality_review_state: "pending",
    last_activity_at: now,
    priority: 1,
    latest_checkpoint: null,
    repository_action: { enabled: false, reason: "Configure an editor command in Settings." },
    ...overrides,
  };
}

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "language",
    name: "Language",
    description: "Book and runnable implementation.",
    kind: "book",
    status: "active",
    priority: 1,
    pinned: true,
    archived: false,
    display_order: 1,
    current_milestone: "Author review of five editorial checkpoints.",
    next_action: "Read the five author-review checkpoints.",
    notes: "",
    last_activity_at: now,
    created_at: now,
    updated_at: now,
    repositories: [
      {
        id: "repo-language",
        name: "language",
        path: "C:\\Projects\\language",
        classification: "book",
        confidence: 0.98,
        evidence: ["README.md describes a book"],
        role: "manuscript",
        source_root: "C:\\Projects",
        is_git: true,
        branch: "main",
        commit_hash: "abcdef1234567890",
        last_commit_at: now,
        dirty: false,
        accessible: true,
        candidate: false,
        last_observed_at: now,
        notes: "",
      },
    ],
    book: null,
    outcomes: [
      {
        id: "books",
        name: "Books and publishing",
        description: "Finished books.",
        status: "active",
        url: null,
        notes: "",
      },
    ],
    applications: [{ id: "writer", name: "Writer", category: "writing" }],
    latest_checkpoint: null,
    open_task_count: 1,
    pending_recommendation_count: 1,
    ...overrides,
  };
}

export function makeActivity(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: "evt-1",
    type: "checkpoint",
    title: "Checkpoint: Math",
    detail: "Reviewed the Lorentz proof validation.",
    project_id: "math",
    project_name: "Math",
    application_id: null,
    application_name: null,
    process_id: null,
    source: "mission-control",
    source_id: null,
    evidence_ref: null,
    provenance: "user",
    occurred_at: now,
    observed_at: now,
    metadata: {},
    ...overrides,
  };
}

export function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: "task-1",
    project_id: "math",
    project_name: "Math",
    title: "Inspect proof obligations",
    description: "",
    status: "open",
    priority: 1,
    source: "user",
    due_at: null,
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

export function makeAdapter(overrides: Partial<Adapter> = {}): Adapter {
  return {
    id: "adapter-project-math",
    adapter: "math",
    application_id: null,
    application_name: null,
    project_id: "math",
    project_name: "Math",
    available: true,
    capabilities: ["qualification_evidence"],
    detail: "Read 4 MATH01 claim assessments from report.json.",
    error: null,
    last_checked_at: now,
    stale_after_seconds: 600,
    stale: false,
    ...overrides,
  };
}

export function makeDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  const language = makeBook();
  const inference = makeBook({
    id: "book-inference",
    project_id: "inference",
    project_name: "Inference",
    title: "Inference From First Principles",
    status: "drafting",
    current_milestone: "Chapters 01-28 have starter manuscripts.",
    next_action: "Choose the next chapter to draft.",
    priority: 2,
  });
  const math = makeBook({
    id: "book-math",
    project_id: "math",
    project_name: "Math",
    title: "Adversarial Mathematics From First Principles",
    status: "verification",
    current_milestone: "MATH01-R1 recorded.",
    next_action: "Review unresolved proof obligations.",
    priority: 3,
  });
  const project = makeProject({
    id: "math",
    name: "Math",
    next_action: "Review unresolved proof obligations.",
    book: math,
  });
  return {
    generated_at: now,
    date: "2026-10-23",
    focus: project,
    checkpoint: {
      id: "cp-1",
      project_id: "math",
      project_name: "Math",
      summary: "Lorentz proof validation reviewed.",
      last_completed: "Read MATH01 report",
      next_action: "Inspect additional proof obligations.",
      blockers: "",
      evidence_refs: ["artifacts/math01/report.json"],
      milestone: "MATH01-R1",
      source: "user",
      created_at: now,
    },
    books: [language, inference, math],
    applications: [makeApplication()],
    activity: [makeActivity()],
    outcomes: [
      {
        id: "books",
        name: "Books and publishing",
        description: "Finished books.",
        status: "active",
        url: null,
        notes: "",
      },
    ],
    tasks: [makeTask()],
    recommendations: [],
    adapters: [makeAdapter()],
    briefing: null,
    stats: {
      priority_books: 3,
      applications: 1,
      running_applications: 0,
      pending_reviews: 0,
      open_tasks: 1,
      repositories_discovered: 84,
      adapters_available: 1,
      priority_projects: 3,
    },
    ...overrides,
  };
}

export function makeSettings(overrides: Partial<Settings> = {}): Settings {
  return {
    discovery: {
      exclusions: [".git", "node_modules"],
      max_depth: 1,
      max_candidates: 500,
      timeout_seconds: 120,
      git_timeout_seconds: 5,
    },
    editor: { command: "", arguments: [], append_path: true },
    browser: { open_mode: "new_tab" },
    processes: { max_managed: 5, health_check_interval_seconds: 30, log_tail_lines: 200 },
    adapters: { refresh_interval_minutes: 10, timeout_seconds: 5 },
    retention: { activity_days: 365, briefing_days: 90, log_days: 30 },
    ai: {
      enabled: false,
      consent: false,
      provider: "openai-compatible",
      base_url: "",
      model: "",
      api_key_env: "OPENAI_API_KEY",
      timeout_seconds: 45,
    },
    startup: { profile_enabled: false, profile_applications: [] },
    ui: { theme: "system" },
    discovery_roots: [
      { path: "C:\\Projects", enabled: true, added_at: now },
      { path: "C:\\books", enabled: true, added_at: now },
    ],
    ai_configured: false,
    ai_key_present: false,
    ...overrides,
  };
}

export function makeProjectDetail(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  const base = makeProject();
  return {
    ...base,
    repository_action: { enabled: false, reason: "Configure an editor command in Settings." },
    checkpoints: [],
    tasks: [makeTask()],
    decisions: [],
    recommendations: [
      {
        id: "rec-1",
        project_id: "language",
        project_name: "Language",
        title: "Review MATH01 obligation: Cross-kernel equivalence",
        rationale: "The recorded assessment leaves this obligation open.",
        evidence: ["artifacts/math01/report.json"],
        source_application: "math",
        source_ref: "artifacts/math01/report.json",
        external_id: "math-obligation-1",
        provenance: "derived_observation",
        review_state: "pending",
        created_at: now,
        updated_at: now,
      },
    ],
    activity: [makeActivity()],
    adapters: [makeAdapter()],
    ...overrides,
  };
}
