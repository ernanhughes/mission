import { useApi } from "../../api/useApi";

export type AitestSummary = {
  projects: number;
  total_tests: number;
  assessed: number;
  unassessed: number;
  healthy: number;
  failing: number;
  quarantined: number;
  deferred: number;
  repair_needed: number;
};

export type AitestProject = {
  project_id: string;
  name: string;
  root: string;
  remote_url: string;
  mc_project_id: string;
  integration_state: string;
  policy: string;
  aitest_version: string;
  last_receipt_id: string;
  last_status: string;
  last_seen_at: string;
};

export type AitestTest = {
  project_id: string;
  logical_id: string;
  relpath: string;
  class_name: string;
  func_name: string;
  duration_ms: number;
  band: string;
  lifecycle: string;
  last_outcome: string;
  last_seen_at: string;
};

export type AitestReceipt = {
  execution_id: string;
  project_id: string;
  snapshot_id: string;
  status: string;
  discovered: number;
  executed: number;
  passed: number;
  failed: number;
  skipped: number;
  quarantined: number;
  deferred: number;
  timed_out: number;
  unobserved: number;
  duration_ms: number;
  created_at: string;
};

export type AitestIssue = {
  id: number;
  project_id: string;
  test_logical_id: string;
  kind: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export function useTestsSummary() {
  return useApi<AitestSummary>("/api/tests/summary");
}

export function useTestsProjects() {
  return useApi<AitestProject[]>("/api/tests/projects");
}
