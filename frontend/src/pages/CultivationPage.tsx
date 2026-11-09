import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Lock, Medal, Plus, Sprout } from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import { Modal } from "../components/Modal";
import {
  EmptyState,
  ErrorState,
  InlineError,
  LoadingBlock,
  PageHeader,
  Section,
  Stat,
  Tag,
} from "../components/ui";
import { formatDateTime } from "../lib/format";
import type {
  CultivationConfig,
  CultivationEvent,
  CultivationGoal,
  CultivationItem,
  CultivationMeasurement,
  CultivationRank,
} from "../types/api";

function progressBar(percent: number | null): React.ReactNode {
  return (
    <span className="hud-bar hud-bar-block" aria-hidden="true">
      <span style={{ width: `${percent ?? 0}%` }} />
    </span>
  );
}

function progressText(goal: CultivationGoal): string {
  const detail = goal.progress;
  if (detail.estimate_label) return detail.estimate_label;
  if (detail.current == null) return detail.unknown_reason ?? "Unknown";
  const formatted = Number.isInteger(detail.current) ? `${detail.current}` : detail.current.toFixed(1);
  return `${formatted} / ${detail.target} ${detail.unit}`;
}

export function CultivationPage() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("goal") ?? "";
  const goals = useApi<CultivationGoal[]>("/api/cultivation/goals");
  const ranks = useApi<CultivationRank[]>("/api/cultivation/ranks");
  const config = useApi<CultivationConfig>("/api/cultivation/config");
  const [showNew, setShowNew] = useState(false);

  const selected = useMemo(
    () => (goals.data ?? []).find((goal) => goal.id === selectedId) ?? null,
    [goals.data, selectedId],
  );

  function select(id: string) {
    setParams(id ? { goal: id } : {}, { replace: true });
  }

  async function archive(goal: CultivationGoal, state: string) {
    try {
      await api.patch(`/api/cultivation/goals/${goal.id}`, { state });
      toast.push("success", state === "archived" ? "Goal archived" : `Goal marked ${state}`);
      goals.reload();
    } catch (caught) {
      toast.push("error", "Update failed", errorMessage(caught));
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Cultivation"
        title="Achievement paths"
        description="Meaningful completed work, tracked per goal with item lifecycles, milestones and ranks. No model calls."
        actions={
          <button className="button button-primary button-small" onClick={() => setShowNew(true)}>
            <Plus size={14} /> New goal
          </button>
        }
      />

      {goals.loading && !goals.data ? <LoadingBlock label="Loading goals" /> : null}
      {goals.error ? <ErrorState message={goals.error.message} onRetry={goals.reload} /> : null}

      <div className="cultivation-grid">
        <div>
          <Section title="Goals" description={`${goals.data?.length ?? 0} tracked`}>
            {(goals.data ?? []).length === 0 ? (
              <EmptyState title="No goals yet" description="Create your first goal to begin." icon={<Sprout size={20} />} />
            ) : null}
            <ul className="goal-list">
              {(goals.data ?? []).map((goal) => (
                <li key={goal.id} className={goal.id === selectedId ? "goal-card goal-card-active" : "goal-card"}>
                  <div className="activity-head">
                    <button className="link-button" onClick={() => select(goal.id)}>
                      <strong>{goal.name}</strong>
                    </button>
                    {goal.privacy === "private" ? (
                      <Tag>
                        <Lock size={11} /> Private
                      </Tag>
                    ) : null}
                    {goal.state !== "active" ? <Tag>{goal.state}</Tag> : null}
                    {goal.progress.achieved ? <Tag tone="accent">Achieved</Tag> : null}
                  </div>
                  <div className="muted">{progressText(goal)}</div>
                  {progressBar(goal.progress.percent)}
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Cultivation ranks" description="Thematic labels for sustained accomplishment.">
            {ranks.loading && !ranks.data ? <LoadingBlock label="Loading ranks" compact /> : null}
            {(ranks.data ?? []).map((rank) => (
              <p key={rank.id} className="row-line">
                <Medal size={13} aria-hidden="true" /> <strong>{rank.name}</strong>
                <span className="muted"> — {rank.concept}</span>
                {rank.qualified ? <Tag tone="accent">Attained</Tag> : null}
              </p>
            ))}
          </Section>
        </div>

        <div>
          {selected ? (
            <GoalDetail
              key={selected.id}
              goal={selected}
              stages={config.data?.stages ?? []}
              onChanged={() => {
                goals.reload();
                ranks.reload();
              }}
              onClose={() => select("")}
              onArchive={(state) => void archive(selected, state)}
            />
          ) : (
            <Section title="Goal detail" description="Select a goal to manage its items, measurements and history.">
              <EmptyState title="No goal selected" description="Choose a goal on the left." icon={<Sprout size={20} />} />
            </Section>
          )}
        </div>
      </div>

      <ConfigSection config={config} onChanged={() => config.reload()} />

      {showNew ? (
        <NewGoalModal
          onClose={() => setShowNew(false)}
          onCreated={(id) => {
            setShowNew(false);
            goals.reload();
            select(id);
          }}
        />
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ detail
function GoalDetail(props: {
  goal: CultivationGoal;
  stages: Array<{ id: string; label: string; color: string }>;
  onChanged: () => void;
  onClose: () => void;
  onArchive: (state: string) => void;
}) {
  const { goal } = props;
  const toast = useToast();
  const items = useApi<CultivationItem[]>(apiPath(`/api/cultivation/goals/${goal.id}/items`));
  const measurements = useApi<CultivationMeasurement[]>(
    goal.measurement_type === "count" || goal.measurement_type === "qualified_count"
      ? null
      : `/api/cultivation/goals/${goal.id}/measurements`,
  );
  const events = useApi<CultivationEvent[]>(apiPath(`/api/cultivation/goals/${goal.id}/events`, { limit: 100 }));
  const evidence = useApi<Array<{ id: string; kind: string; reference: string; note: string; verified: boolean }>>(
    `/api/cultivation/goals/${goal.id}/evidence`,
  );
  const [itemTitle, setItemTitle] = useState("");
  const [itemStage, setItemStage] = useState("idea");
  const [measureValue, setMeasureValue] = useState("");
  const [measureNote, setMeasureNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const stageLabel = (id: string) => props.stages.find((stage) => stage.id === id)?.label ?? id;
  const metric = goal.measurement_type !== "count" && goal.measurement_type !== "qualified_count";

  async function addItem(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/api/cultivation/items", {
        title: itemTitle,
        goal_ids: [goal.id],
        stage: itemStage,
      });
      setItemTitle("");
      toast.push("success", "Item added");
      items.reload();
      props.onChanged();
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  async function advance(itemId: string, stage: string) {
    try {
      await api.patch(`/api/cultivation/items/${itemId}/goals/${goal.id}/stage`, { stage });
      items.reload();
      events.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Stage change failed", errorMessage(caught));
    }
  }

  async function recordMeasurement(event: FormEvent) {
    event.preventDefault();
    const value = Number(measureValue);
    if (!Number.isFinite(value)) {
      toast.push("error", "Value must be a number");
      return;
    }
    try {
      await api.post(`/api/cultivation/goals/${goal.id}/measurements`, {
        value,
        note: measureNote,
      });
      setMeasureValue("");
      setMeasureNote("");
      measurements.reload?.();
      events.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Measurement failed", errorMessage(caught));
    }
  }

  const grouped = useMemo(() => {
    const byStage = new Map<string, CultivationItem[]>();
    for (const item of items.data ?? []) {
      const membership = item.memberships.find((entry) => entry.goal_id === goal.id);
      const stage = membership?.stage ?? "idea";
      byStage.set(stage, [...(byStage.get(stage) ?? []), item]);
    }
    return Array.from(byStage.entries());
  }, [items.data, goal.id]);

  const stageOrder = useMemo(() => {
    const known = props.stages.length ? props.stages.map((stage) => stage.id) : [];
    const seen = (items.data ?? []).flatMap((item) =>
      item.memberships.filter((entry) => entry.goal_id === goal.id).map((entry) => entry.stage),
    );
    return Array.from(new Set([...known, ...seen]));
  }, [props.stages, items.data, goal.id]);

  return (
    <Section
      title={goal.name}
      description={`${progressText(goal)}${goal.baseline_note ? ` · ${goal.baseline_note}` : ""}`}
      actions={
        <>
          {goal.state === "active" ? (
            <button className="button button-ghost button-small" onClick={() => props.onArchive("paused")}>
              Pause
            </button>
          ) : null}
          {goal.state !== "achieved" ? (
            <button className="button button-secondary button-small" onClick={() => props.onArchive("achieved")}>
              Mark achieved
            </button>
          ) : null}
          {goal.state !== "archived" ? (
            <button className="button button-ghost button-small" onClick={() => props.onArchive("archived")}>
              Archive
            </button>
          ) : (
            <button className="button button-ghost button-small" onClick={() => props.onArchive("active")}>
              Reactivate
            </button>
          )}
          <button className="button button-ghost button-small" onClick={props.onClose}>
            Close
          </button>
        </>
      }
    >
      <div className="stat-strip">
        <Stat label="Progress" value={progressText(goal)} />
        <Stat label="Items in pipeline" value={Object.values(goal.progress.pipeline).reduce((a, b) => a + b, 0)} />
        <Stat label="Next milestone" value={goal.progress.next_milestone ?? "—"} />
      </div>
      {progressBar(goal.progress.percent)}
      {goal.completion_criteria ? <p className="muted">Counts when: {goal.completion_criteria}</p> : null}
      {goal.progress.milestones_reached.length > 0 ? (
        <p className="muted">Milestones reached: {goal.progress.milestones_reached.join(", ")}</p>
      ) : null}

      {metric ? (
        <Section title="Measurements" description="Dated observations. No inference.">
          <form className="inline-form" onSubmit={(event) => void recordMeasurement(event)}>
            <input value={measureValue} onChange={(event) => setMeasureValue(event.target.value)} placeholder={`Value (${goal.unit})`} inputMode="decimal" required />
            <input value={measureNote} onChange={(event) => setMeasureNote(event.target.value)} placeholder="Note (optional)" />
            <button className="button button-primary button-small" type="submit">
              Record
            </button>
          </form>
          {(measurements.data ?? []).slice(0, 10).map((entry) => (
            <p key={entry.id} className="row-line">
              <strong>{entry.value}</strong> {goal.unit}
              <span className="muted"> · {formatDateTime(entry.observed_at)}{entry.note ? ` · ${entry.note}` : ""}</span>
            </p>
          ))}
        </Section>
      ) : (
        <Section title="Add item" description="Artefacts move through stages; only the qualifying stage counts.">
          <form className="inline-form" onSubmit={(event) => void addItem(event)}>
            <InlineError message={error} />
            <input value={itemTitle} onChange={(event) => setItemTitle(event.target.value)} placeholder="Item title" required />
            <select value={itemStage} onChange={(event) => setItemStage(event.target.value)} aria-label="Initial stage">
              {(props.stages.length ? props.stages : [{ id: "idea", label: "Idea", color: "grey" }]).map((stage) => (
                <option value={stage.id} key={stage.id}>
                  {stage.label}
                </option>
              ))}
            </select>
            <button className="button button-primary button-small" type="submit">
              <Plus size={13} /> Add
            </button>
          </form>
        </Section>
      )}

      <Section title="Pipeline" description="In-progress work by stage; completed counts stay separate.">
        {items.loading && !items.data ? <LoadingBlock label="Loading items" compact /> : null}
        {stageOrder.map((stage) => {
          const inStage = (items.data ?? []).filter((item) =>
            item.memberships.some((entry) => entry.goal_id === goal.id && entry.stage === stage),
          );
          if (inStage.length === 0) return null;
          return (
            <div key={stage}>
              <h4>
                {stageLabel(stage)} ({inStage.length})
              </h4>
              {inStage.map((item) => {
                const membership = item.memberships.find((entry) => entry.goal_id === goal.id);
                return (
                  <div key={item.id} className="panel review-card">
                    <div className="activity-head">
                      <strong>{item.title}</strong>
                      {membership?.qualified ? <Tag tone="accent">Qualified</Tag> : null}
                      {membership?.evidence_status !== "none" ? <Tag>{membership?.evidence_status}</Tag> : null}
                    </div>
                    <div className="activity-actions">
                      {(props.stages.length ? props.stages : [{ id: stage, label: stage, color: "" }]).map((candidate) =>
                        candidate.id === stage ? null : (
                          <button
                            key={candidate.id}
                            className="button button-ghost button-small"
                            onClick={() => void advance(item.id, candidate.id)}
                          >
                            → {candidate.label}
                          </button>
                        ),
                      )}
                      {goal.measurement_type === "qualified_count" && membership && !membership.qualified ? (
                        <QualifyButton itemId={item.id} goalId={goal.id} onDone={() => { items.reload(); props.onChanged(); }} />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
        {grouped.length === 0 && !(items.loading && !items.data) ? <p className="muted">No items yet.</p> : null}
      </Section>

      <Section title="History" description="Every change, correction and milestone. Newest first.">
        {(events.data ?? []).slice(0, 30).map((event) => (
          <p key={event.id} className="row-line">
            <span className="tag">{event.event_type.replace(/_/g, " ")}</span>{" "}
            {event.item_title ? <strong>{event.item_title}</strong> : null}{" "}
            {event.from_value || event.to_value ? (
              <span className="muted">
                {event.from_value ?? "—"} → {event.to_value ?? "—"}
              </span>
            ) : null}{" "}
            {event.note ? <span>{event.note}</span> : null}{" "}
            <span className="muted">{formatDateTime(event.created_at)}</span>
          </p>
        ))}
        {(events.data ?? []).length === 0 ? <p className="muted">No history yet.</p> : null}
      </Section>

      <Section title="Evidence" description="Verification references for completed or claimed items.">
        {(evidence.data ?? []).slice(0, 20).map((entry) => (
          <p key={entry.id} className="row-line">
            <code>{entry.kind}</code> {entry.reference}
            <span className="muted">
              {" "}· {entry.note} · {entry.verified ? "verified" : "unverified"}
            </span>
          </p>
        ))}
      </Section>
    </Section>
  );
}

function QualifyButton(props: { itemId: string; goalId: string; onDone: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  async function qualify() {
    try {
      await api.patch(`/api/cultivation/items/${props.itemId}/goals/${props.goalId}/qualify`, {
        qualified: true,
        quality_evidence: { checked: new Date().toISOString(), note },
        note: note || "Meets the qualification standard.",
      });
      toast.push("success", "Qualification recorded");
      props.onDone();
    } catch (caught) {
      toast.push("error", "Qualification failed", errorMessage(caught));
    }
  }
  if (!open) {
    return (
      <button className="button button-secondary button-small" onClick={() => setOpen(true)}>
        Record qualification
      </button>
    );
  }
  return (
    <>
      <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Qualification note" aria-label="Qualification note" />
      <button className="button button-primary button-small" onClick={() => void qualify()}>
        Confirm
      </button>
    </>
  );
}

// --------------------------------------------------------------- new goal
function NewGoalModal(props: { onClose: () => void; onCreated: (id: string) => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [target, setTarget] = useState("100");
  const [unit, setUnit] = useState("items");
  const [measurementType, setMeasurementType] = useState("count");
  const [category, setCategory] = useState("general");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function create(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const goal = await api.post<{ id: string }>("/api/cultivation/goals", {
        name,
        target_value: Number(target),
        unit,
        measurement_type: measurementType,
        category,
      });
      toast.push("success", "Goal created");
      props.onCreated(goal.id);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title="New goal" onClose={props.onClose}>
      <form className="form-stack" onSubmit={(event) => void create(event)}>
        <InlineError message={error} />
        <label className="field">
          <span>Name</span>
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <div className="form-grid two">
          <label className="field">
            <span>Target</span>
            <input value={target} onChange={(event) => setTarget(event.target.value)} inputMode="decimal" required />
          </label>
          <label className="field">
            <span>Unit</span>
            <input value={unit} onChange={(event) => setUnit(event.target.value)} required />
          </label>
        </div>
        <div className="form-grid two">
          <label className="field">
            <span>Measurement</span>
            <select value={measurementType} onChange={(event) => setMeasurementType(event.target.value)}>
              <option value="count">Count</option>
              <option value="threshold_up">Threshold (increasing)</option>
              <option value="threshold_down">Threshold (decreasing)</option>
              <option value="recurring">Recurring</option>
              <option value="qualified_count">Qualified-item count</option>
            </select>
          </label>
          <label className="field">
            <span>Category</span>
            <input value={category} onChange={(event) => setCategory(event.target.value)} />
          </label>
        </div>
        <button className="button button-primary" type="submit" disabled={saving || !name.trim()}>
          {saving ? "Creating…" : "Create goal"}
        </button>
      </form>
    </Modal>
  );
}

// ------------------------------------------------------------------ config
function ConfigSection(props: { config: ReturnType<typeof useApi<import("../types/api").CultivationConfig>>; onChanged: () => void }) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [stagesText, setStagesText] = useState("");
  const [error, setError] = useState<string | null>(null);

  function begin() {
    setStagesText(JSON.stringify(props.config.data?.stages ?? [], null, 2));
    setError(null);
    setEditing(true);
  }

  async function save() {
    let stages: unknown;
    try {
      stages = JSON.parse(stagesText);
    } catch {
      setError("Stages must be valid JSON.");
      return;
    }
    try {
      await api.patch("/api/cultivation/config", { stages });
      toast.push("success", "Stages updated");
      setEditing(false);
      props.onChanged();
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  return (
    <Section
      title="Configuration"
      description="Lifecycle stages are shared across goals. Ranks are thematic labels, not scores."
      actions={
        editing ? (
          <>
            <button className="button button-primary button-small" onClick={() => void save()}>
              Save stages
            </button>
            <button className="button button-ghost button-small" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button className="button button-secondary button-small" onClick={begin}>
            Edit stages
          </button>
        )
      }
    >
      <InlineError message={error} />
      {editing ? (
        <textarea rows={10} value={stagesText} onChange={(event) => setStagesText(event.target.value)} aria-label="Stages JSON" />
      ) : (
        <p className="muted">
          {(props.config.data?.stages ?? []).map((stage) => stage.label).join(" → ") || "No stages configured."}
        </p>
      )}
    </Section>
  );
}
