/** Shared verdict presentation. Only .tag-accent/.tag-danger/.tag-default
 *  exist in styles; meaning lives in the label text, never color alone. */

export type Tone = "default" | "accent" | "danger";

export function completionTone(value: string | null): { tone: Tone; label: string } {
  switch ((value ?? "unknown").toLowerCase()) {
    case "complete":
      return { tone: "accent", label: "Complete · verified" };
    case "partial":
      return { tone: "default", label: "Partial" };
    case "incomplete":
      return { tone: "danger", label: "Incomplete" };
    case "blocked":
      return { tone: "danger", label: "Blocked" };
    default:
      return { tone: "default", label: "Unknown" };
  }
}

export function assessmentTone(value: string | null): { tone: Tone; label: string } {
  switch ((value ?? "unknown").toLowerCase()) {
    case "sound":
    case "good":
      return { tone: "accent", label: value ?? "Unknown" };
    case "concerns":
    case "mixed":
      return { tone: "default", label: value ?? "Unknown" };
    case "poor":
      return { tone: "danger", label: value ?? "Unknown" };
    default:
      return { tone: "default", label: "Unknown" };
  }
}

export function verdictTone(value: string): { tone: Tone; label: string } {
  const v = (value ?? "").toLowerCase();
  if (v === "satisfied_verified" || v === "verified_commit_exists" || v === "verified_review_exists")
    return { tone: "accent", label: value };
  if (v === "not_satisfied" || v === "contradicted" || v === "unsupported_claim" || v === "defect")
    return { tone: "danger", label: value };
  return { tone: "default", label: value };
}

export function kindLabel(kind: string): string {
  switch ((kind ?? "").toLowerCase()) {
    case "task":
      return "Task";
    case "stage":
      return "Stage";
    case "programme":
      return "Programme";
    case "chain":
      return "Session chain";
    case "cluster":
      return "Linked work";
    case "unresolved":
      return "Unresolved";
    default:
      return kind || "Work";
  }
}

export function formatTime(ms: number): string {
  if (!ms) return "Unknown time";
  try {
    return new Date(ms).toLocaleString(undefined, {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "Unknown time";
  }
}

/** W6B: human-readable gap classes for finding groups. */
export function gapClassLabel(gap: string): string {
  switch ((gap ?? "").toLowerCase()) {
    case "missing_test_evidence":
      return "Missing test evidence";
    case "merge_corroborated_push_unproven":
      return "Merge corroborated · push unproven";
    case "missing_merge_provenance":
      return "Missing merge provenance";
    case "missing_push_proof":
      return "Missing push/deployment proof";
    case "unresolved_review":
      return "Unresolved independent review";
    case "missing_requirement":
      return "Missing mandatory requirement";
    case "confirmed_defect":
      return "Confirmed defect";
    case "verification_gap":
      return "Verification gap";
    default:
      return "Historical evidence limitation";
  }
}

/** W7: finding → corrective action (evidence recovery first, never code by default). */
export function actionForGap(gap: string, kind: string): string {
  switch ((gap ?? "").toLowerCase()) {
    case "missing_test_evidence":
      return "REPRODUCE_VERIFICATION";
    case "merge_corroborated_push_unproven":
    case "missing_merge_provenance":
    case "missing_push_proof":
      return "RECOVER_EXISTING_EVIDENCE";
    case "unresolved_review":
      return "INDEPENDENT_REVIEW";
    case "missing_requirement":
      return "RECOVER_OR_CONFIRM_REQUIREMENTS";
    case "confirmed_defect":
      return "INVESTIGATE_SUSPECTED_DEFECT";
    default:
      if ((kind ?? "").toLowerCase() === "defect") return "INVESTIGATE_SUSPECTED_DEFECT";
      if ((kind ?? "").toLowerCase() === "missing_requirement") return "RECOVER_OR_CONFIRM_REQUIREMENTS";
      if ((kind ?? "").toLowerCase() === "unsupported_claim") return "RECOVER_EXISTING_EVIDENCE";
      return "REQUEST_USER_DECISION";
  }
}

/** W7: plain-language recommended next step per action category. */
export function actionAdvice(action: string): string {
  switch (action) {
    case "RECOVER_EXISTING_EVIDENCE":
      return "Recover existing evidence first: Git history, reviews, test receipts, programme documents.";
    case "REPRODUCE_VERIFICATION":
      return "Reproduce or locate the test execution; a new passing run proves current state, not the old claim.";
    case "RECOVER_OR_CONFIRM_REQUIREMENTS":
      return "Recover and confirm the original intent before any implementation work.";
    case "INDEPENDENT_REVIEW":
      return "Commission an independent verification of the outstanding review.";
    case "INVESTIGATE_SUSPECTED_DEFECT":
      return "Investigate the suspected defect; do not rewrite code until it is confirmed.";
    default:
      return "Review the group and decide the next step explicitly.";
  }
}
export function gapClosureCriteria(gap: string): string {
  switch ((gap ?? "").toLowerCase()) {
    case "missing_test_evidence":
      return "Attach the execution record (suite, revision, result). A later passing run at the same revision closes members individually.";
    case "merge_corroborated_push_unproven":
      return "Supply the push/deployment record or remote ref. Merged-into-main alone never proves a push.";
    case "missing_merge_provenance":
      return "Identify the merge SHA and confirm it is an ancestor of the main line.";
    case "missing_push_proof":
      return "Supply the remote ref or deployment record for the claimed push.";
    case "unresolved_review":
      return "Record the independent review verdict for the affected revision.";
    case "missing_requirement":
      return "Satisfy the mandatory requirement with evidence, or record an authorized deferral.";
    case "confirmed_defect":
      return "Fix the defect and verify against the cited counter-evidence.";
    default:
      return "Supply the missing provenance, or record why it is unavailable. Groups never close automatically.";
  }
}
