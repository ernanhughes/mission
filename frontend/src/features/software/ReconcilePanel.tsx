import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { Modal } from "../../components/Modal";
import { useToast } from "../../components/Toast";
import { ErrorState, InlineError, LoadingBlock, Section, Tag } from "../../components/ui";
import type { IdentityPreview } from "../../types/api";

function PolicyNote({ preview }: { preview: IdentityPreview }) {
  const policy = preview.policy;
  return (
    <p className="muted small">
      {policy.auto_register
        ? `Automatic registration is approved${policy.approved_root ? ` for ${policy.approved_root}` : ""}${policy.approved_at ? ` since ${policy.approved_at}` : ""}. New unambiguous repositories register on explicit request.`
        : "Automatic registration is not approved. Eligible repositories only register after explicit bulk approval."}
    </p>
  );
}

export function ReconcilePanel({ onClose, onApplied }: { onClose: () => void; onApplied: () => void }) {
  const toast = useToast();
  const preview = useApi<IdentityPreview>("/api/projects/identity/preview");
  const [approvePolicy, setApprovePolicy] = useState(true);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function apply() {
    setBusy("apply");
    setError(null);
    try {
      const response = await api.post<{ counts: { created: number; skipped: number }; backup: string | null }>(
        "/api/projects/identity/apply",
        { all_eligible: true, confirm: confirmed, approve_policy: approvePolicy },
      );
      setResult(
        `Registered ${response.counts.created} workspaces (${response.counts.skipped} skipped)${response.backup ? ` · database backed up to ${response.backup}` : ""}.`,
      );
      toast.push("success", "Cutover applied", `${response.counts.created} registered`);
      preview.reload();
      onApplied();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function autoRegister() {
    setBusy("auto");
    setError(null);
    try {
      const response = await api.post<{ counts: { created: number; skipped: number } }>(
        "/api/projects/identity/auto-register",
        { confirm: true },
      );
      setResult(`Auto-registered ${response.counts.created} workspaces (${response.counts.skipped} skipped).`);
      preview.reload();
      onApplied();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function rollback() {
    setBusy("rollback");
    setError(null);
    try {
      const response = await api.post<{ counts: { removed: number; retained: number } }>(
        "/api/projects/identity/rollback",
        { confirm: confirmed },
      );
      setResult(
        `Rolled back ${response.counts.removed} pristine workspaces; ${response.counts.retained} retained with user records.`,
      );
      preview.reload();
      onApplied();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  const data = preview.data;

  return (
    <Modal
      title="Discovery & reconciliation"
      eyebrow="Software identity"
      onClose={onClose}
      wide
      footer={
        <>
          <button className="button button-ghost" type="button" onClick={onClose}>
            Close
          </button>
        </>
      }
    >
      {preview.loading && !data ? <LoadingBlock label="Loading reconciliation preview" /> : null}
      {preview.error ? <ErrorState message={preview.error.message} onRetry={preview.reload} /> : null}
      {data ? (
        <div className="form-stack">
          <InlineError message={error} />
          {result ? <p className="muted">{result}</p> : null}
          <PolicyNote preview={data} />
          <Section
            title={`Eligible for registration (${data.counts.eligible ?? 0})`}
            description="Unambiguous software repositories. Identity is the Git repo_uid or normalized path — never a display name."
          >
            {(data.eligible ?? []).length === 0 ? (
              <p className="muted small">Nothing eligible. Either everything is registered or everything needs review.</p>
            ) : (
              <ul className="plain-list">
                {(data.eligible ?? []).slice(0, 50).map((item) => (
                  <li key={item.path} className="muted small">
                    <strong>{item.name}</strong> · {item.classification.replace(/_/g, " ")} ·{" "}
                    <code className="mono">{item.path}</code>
                    {item.links.length > 1 ? ` · +${item.links.length - 1} worktree(s)` : ""}
                    {item.application_id ? ` · app: ${item.application_id}` : ""}
                  </li>
                ))}
              </ul>
            )}
            {(data.eligible ?? []).length > 50 ? (
              <p className="muted small">Showing 50 of {data.eligible.length} eligible repositories.</p>
            ) : null}
          </Section>
          <Section
            title={`Needs owner review (${data.counts.needs_review ?? 0})`}
            description="Ambiguous classification, book-legacy domain, or missing paths. Nothing here registers automatically."
          >
            {(data.needs_review ?? []).length === 0 ? (
              <p className="muted small">Review queue is clear.</p>
            ) : (
              <ul className="plain-list">
                {(data.needs_review ?? []).slice(0, 50).map((item) => (
                  <li key={item.path} className="muted small">
                    <strong>{item.name}</strong> · {item.classification.replace(/_/g, " ")} · {item.reason}{" "}
                    <code className="mono">{item.path}</code>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <p className="muted small">
            Skipped as already linked or generated noise: {data.counts.skipped ?? 0} · Book-legacy
            preserved: {data.counts.book_legacy_preserved ?? 0}
          </p>
          {(data.notes ?? []).map((note) => (
            <p className="muted small" key={note}>
              {note}
            </p>
          ))}
          <div className="form-stack">
            <label className="checkbox">
              <input type="checkbox" checked={approvePolicy} onChange={(event) => setApprovePolicy(event.target.checked)} />
              Approve the policy: future unambiguous repositories may auto-register on explicit request
            </label>
            <label className="checkbox">
              <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
              I confirm this cutover (backs up the database first; idempotent on re-run)
            </label>
            <div className="button-row">
              <button
                className="button button-primary button-small"
                disabled={busy !== null || !confirmed}
                onClick={() => void apply()}
              >
                {busy === "apply" ? "Applying…" : "Approve & register eligible"}
              </button>
              <button
                className="button button-secondary button-small"
                disabled={busy !== null || !data.policy.auto_register}
                onClick={() => void autoRegister()}
                title={data.policy.auto_register ? "Register currently-eligible repositories" : "Enable the policy first via bulk approval"}
              >
                {busy === "auto" ? "Registering…" : "Auto-register new"}
              </button>
              <button
                className="button button-ghost button-small"
                disabled={busy !== null || !confirmed}
                onClick={() => void rollback()}
              >
                {busy === "rollback" ? "Rolling back…" : "Roll back pristine registrations"}
              </button>
            </div>
            <p className="muted small">
              <Tag>Rollback keeps every project that has checkpoints, tasks, decisions, recommendations or activity.</Tag>
            </p>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
