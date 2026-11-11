import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { CalendarRange, Lock, Medal, Plus, Sprout } from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import { Modal } from "../components/Modal";
import { SkillDetail } from "../features/cultivation/SoftwareSkill";
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
  CultivationCycle,
  CultivationEvent,
  CultivationGoal,
  CultivationItem,
  CultivationMeasurement,
  CultivationRank,
  CultivationSkill,
  CultivationSource,
} from "../types/api";
import { barState, currentLabel } from "../features/cultivation/progress";

function GoalBar(props: { goal: CultivationGoal }) {
  const percent = props.goal.progress.percent ?? 0;
  const clamped = Math.min(100, Math.max(0, percent));
  return (
    <span
      className="hud-bar hud-bar-block"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      aria-label={currentLabel(props.goal.progress)}
      data-state={barState(props.goal.progress)}
    >
      <span style={{ width: `${clamped}%` }} />
    </span>
  );
}

function progressText(goal: CultivationGoal): string {
  return currentLabel(goal.progress);
}

export function CultivationPage() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("goal") ?? "";
  const skillId = params.get("skill") ?? "";
  const goals = useApi<CultivationGoal[]>("/api/cultivation/goals");
  const skills = useApi<CultivationSkill[]>("/api/cultivation/skills");
  const ranks = useApi<CultivationRank[]>("/api/cultivation/ranks");
  const config = useApi<CultivationConfig>("/api/cultivation/config");
  const cycles = useApi<CultivationCycle[]>("/api/cultivation/cycles");
  const sources = useApi<CultivationSource[]>("/api/cultivation/sources");
  const [showNew, setShowNew] = useState(false);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [stateFilter, setStateFilter] = useState("active");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [newSkill, setNewSkill] = useState("");

  const selected = useMemo(
    () => (goals.data ?? []).find((goal) => goal.id === selectedId) ?? null,
    [goals.data, selectedId],
  );

  const categories = useMemo(
    () => Array.from(new Set((goals.data ?? []).map((goal) => goal.category))).sort(),
    [goals.data],
  );

  function select(id: string) {
    setParams(id ? { goal: id } : skillId ? { skill: skillId } : {}, { replace: true });
  }

  function openSkill(id: string) {
    setParams({ skill: id }, { replace: true });
  }

  function toggleSkill(id: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function createSkill(event: FormEvent) {
    event.preventDefault();
    const name = newSkill.trim();
    if (!name) return;
    try {
      await api.post("/api/cultivation/skills", { name });
      setNewSkill("");
      toast.push("success", "Skill created");
      reloadAll();
    } catch (caught) {
      toast.push("error", "Skill creation failed", errorMessage(caught));
    }
  }

  async function toggleSkillPin(skill: { id: string; pinned: boolean }) {
    try {
      await api.patch(`/api/cultivation/skills/${skill.id}`, { pinned: !skill.pinned });
      reloadAll();
    } catch (caught) {
      toast.push("error", "Pin update failed", errorMessage(caught));
    }
  }

  async function moveSkill(id: string, direction: -1 | 1) {
    const ordered = [...(skills.data ?? [])].sort(
      (a, b) => a.pin_order - b.pin_order || a.name.localeCompare(b.name),
    );
    const index = ordered.findIndex((skill) => skill.id === id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    const [moved] = ordered.splice(index, 1);
    ordered.splice(target, 0, moved);
    try {
      await api.post("/api/cultivation/skills/reorder", { ids: ordered.map((skill) => skill.id) });
      reloadAll();
    } catch (caught) {
      toast.push("error", "Reorder failed", errorMessage(caught));
    }
  }

  async function archiveSkill(id: string) {
    try {
      await api.patch(`/api/cultivation/skills/${id}`, { state: "archived" });
      toast.push("success", "Skill archived");
      reloadAll();
    } catch (caught) {
      toast.push("error", "Archive failed", errorMessage(caught));
    }
  }

  async function unarchiveSkill(id: string) {
    try {
      await api.patch(`/api/cultivation/skills/${id}`, { state: "active" });
      toast.push("success", "Skill reactivated");
      reloadAll();
    } catch (caught) {
      toast.push("error", "Reactivate failed", errorMessage(caught));
    }
  }

  const needle = search.trim().toLowerCase();
  const visibleGoals = useMemo(
    () =>
      (goals.data ?? []).filter((goal) => {
        if (stateFilter === "active" && goal.state !== "active") return false;
        if (stateFilter === "achieved" && goal.state !== "achieved") return false;
        if (category && goal.category !== category) return false;
        if (needle && !`${goal.name} ${goal.description}`.toLowerCase().includes(needle)) return false;
        return true;
      }),
    [goals.data, stateFilter, category, needle],
  );

  const grouped = useMemo(() => {
    const bySkill = new Map<string, CultivationGoal[]>();
    const unassigned: CultivationGoal[] = [];
    for (const goal of visibleGoals) {
      if (goal.skill_id) bySkill.set(goal.skill_id, [...(bySkill.get(goal.skill_id) ?? []), goal]);
      else unassigned.push(goal);
    }
    return { bySkill, unassigned };
  }, [visibleGoals]);

  async function archive(goal: CultivationGoal, state: string) {
    try {
      await api.patch(`/api/cultivation/goals/${goal.id}`, { state });
      toast.push("success", state === "archived" ? "Goal archived" : `Goal marked ${state}`);
      goals.reload();
    } catch (caught) {
      toast.push("error", "Update failed", errorMessage(caught));
    }
  }

  function reloadAll() {
    goals.reload();
    skills.reload();
    ranks.reload();
    cycles.reload();
    sources.reload();
  }

  return (
    <div className="page cultivation-scope">
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

      {goals.error ? <ErrorState message={goals.error.message} onRetry={goals.reload} /> : null}

      <div className="toolbar">
        <label className="search-field">
          <span className="sr-only">Search goals and skills</span>
          <input value={search} placeholder="Search goals…" onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by category</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">All categories</option>
            {categories.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span className="sr-only">Filter by state</span>
          <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
            <option value="active">Active</option>
            <option value="achieved">Achieved</option>
            <option value="all">Active + achieved</option>
          </select>
        </label>
        <span className="toolbar-count">
          {(skills.data ?? []).length} skills · {visibleGoals.length} goals
        </span>
      </div>

      <div className="cultivation-grid">
        <div>
          <Section title="Skills" description="Configurable domains. Expand a skill to see its goals.">
            {skills.loading && !skills.data ? <LoadingBlock label="Loading skills" compact /> : null}
            <form className="inline-form" onSubmit={(event) => void createSkill(event)}>
              <input value={newSkill} onChange={(event) => setNewSkill(event.target.value)} placeholder="New skill name" aria-label="New skill name" />
              <button className="button button-primary button-small" type="submit">
                <Plus size={13} /> Add skill
              </button>
            </form>
            {(skills.data ?? []).map((skill) => {
              const members = grouped.bySkill.get(skill.id) ?? [];
              if (visibleGoals.length > 0 && members.length === 0 && (needle || category)) return null;
              const open = !collapsed.has(skill.id);
              return (
                <div key={skill.id} className="panel review-card">
                  <div className="activity-head">
                    <button className="link-button" onClick={() => toggleSkill(skill.id)} aria-expanded={open}>
                      <strong>{skill.name}</strong>
                    </button>
                    {skill.pinned ? <Tag tone="accent">Pinned</Tag> : null}
                    {skill.state !== "active" ? <Tag>{skill.state}</Tag> : null}
                    <span className="muted">
                      {skill.goals_achieved}/{skill.goals_total} goals · {skill.item_completions} completions
                    </span>
                    <button className="button button-ghost button-small" onClick={() => openSkill(skill.id)}>
                      Open
                    </button>
                  </div>
                  <div className="activity-actions">
                    <button className="button button-ghost button-small" onClick={() => void toggleSkillPin(skill)}>
                      {skill.pinned ? "Unpin" : "Pin"}
                    </button>
                    <button className="button button-ghost button-small" onClick={() => void moveSkill(skill.id, -1)} aria-label={`Move ${skill.name} up`}>
                      ↑
                    </button>
                    <button className="button button-ghost button-small" onClick={() => void moveSkill(skill.id, 1)} aria-label={`Move ${skill.name} down`}>
                      ↓
                    </button>
                    {skill.state !== "archived" ? (
                      <button className="button button-ghost button-small" onClick={() => void archiveSkill(skill.id)}>
                        Archive
                      </button>
                    ) : (
                      <button className="button button-ghost button-small" onClick={() => void unarchiveSkill(skill.id)}>
                        Reactivate
                      </button>
                    )}
                  </div>
                  {open
                    ? members.map((goal) => (
                        <GoalRow key={goal.id} goal={goal} active={goal.id === selectedId} onSelect={select} />
                      ))
                    : null}
                  {open && members.length === 0 ? <p className="muted">No goals in this skill yet.</p> : null}
                </div>
              );
            })}
            {grouped.unassigned.length > 0 ? (
              <div className="panel review-card">
                <div className="activity-head">
                  <strong>Unassigned</strong>
                </div>
                {grouped.unassigned.map((goal) => (
                  <GoalRow key={goal.id} goal={goal} active={goal.id === selectedId} onSelect={select} />
                ))}
              </div>
            ) : null}
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
              skills={skills.data ?? []}
              stages={config.data?.stages ?? []}
              source={(sources.data ?? []).find((row) => row.goal_id === selected.id) ?? null}
              onChanged={reloadAll}
              onClose={() => select("")}
              onArchive={(state) => void archive(selected, state)}
            />
          ) : skillId ? (
            <SkillDetail
              key={skillId}
              skillId={skillId}
              onSelectGoal={select}
              onChanged={reloadAll}
              onClose={() => setParams({}, { replace: true })}
            />
          ) : (
            <Section title="Goal detail" description="Select a goal to manage its items, measurements and history.">
              <EmptyState title="No goal selected" description="Choose a goal on the left." icon={<Sprout size={20} />} />
            </Section>
          )}

          <CycleSection cycles={cycles.data ?? []} goals={goals.data ?? []} onChanged={reloadAll} />
        </div>
      </div>

      <ConfigSection config={config} onChanged={() => config.reload()} />

      {showNew ? (
        <NewGoalModal
          skills={skills.data ?? []}
          onClose={() => setShowNew(false)}
          onCreated={(id) => {
            setShowNew(false);
            goals.reload();
            skills.reload();
            select(id);
          }}
        />
      ) : null}
    </div>
  );
}

function GoalRow(props: { goal: CultivationGoal; active: boolean; onSelect: (id: string) => void }) {
  const { goal } = props;
  const isScripts = goal.id === "scripts_published" || goal.id === "weekly_script";
  return (
    <div className={props.active ? "goal-card goal-card-active" : "goal-card"}>
      <div className="activity-head">
        <button className="link-button" onClick={() => props.onSelect(goal.id)}>
          <strong>{goal.name}</strong>
        </button>
        {goal.privacy === "private" ? (
          <Tag>
            <Lock size={11} /> Private
          </Tag>
        ) : null}
        {goal.state !== "active" ? <Tag>{goal.state}</Tag> : null}
        {goal.progress.achieved ? <Tag tone="accent">Achieved</Tag> : null}
        {isScripts ? (
          <a className="button button-ghost button-small" href="/scripts">
            Open library
          </a>
        ) : null}
      </div>
      <div className="muted">{progressText(goal)}</div>
      <GoalBar goal={goal} />
    </div>
  );
}

// ------------------------------------------------------------ goal detail
function GoalDetail(props: {
  goal: CultivationGoal;
  skills: Array<{ id: string; name: string }>;
  stages: Array<{ id: string; label: string; color: string }>;
  source: {
    id: string;
    name: string;
    path: string;
    last_sync_at: string | null;
    last_status: string;
    last_error: string | null;
    observed: Record<string, unknown>;
  } | null;
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
  const [skillId, setSkillId] = useState(goal.skill_id ?? "");
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stageLabel = (id: string) => props.stages.find((stage) => stage.id === id)?.label ?? id;
  const metric = goal.measurement_type !== "count" && goal.measurement_type !== "qualified_count";

  async function assignSkill(value: string) {
    setSkillId(value);
    try {
      await api.patch(`/api/cultivation/goals/${goal.id}`, { skill_id: value || null });
      toast.push("success", value ? "Goal assigned to skill" : "Goal unassigned");
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Assignment failed", errorMessage(caught));
      setSkillId(goal.skill_id ?? "");
    }
  }

  async function syncSource() {
    if (!props.source) return;
    setSyncing(true);
    try {
      const result = await api.post<{ status: string; observed: Record<string, unknown> }>(
        `/api/cultivation/sources/${props.source.id}/sync`,
        {},
      );
      toast.push(result.status === "ok" ? "success" : "info", result.status === "ok" ? "Source synced" : "Source stale — kept last observation");
      items.reload();
      events.reload();
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Sync failed", errorMessage(caught));
    } finally {
      setSyncing(false);
    }
  }

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

  const stageOrder = useMemo(() => {
    const known = props.stages.map((stage) => stage.id);
    const seen = (items.data ?? []).flatMap((item) =>
      item.memberships.filter((entry) => entry.goal_id === goal.id).map((entry) => entry.stage),
    );
    return Array.from(new Set([...known, ...seen]));
  }, [props.stages, items.data, goal.id]);

  const observed = (props.source?.observed ?? {}) as Record<string, number | string | Array<unknown>>;

  return (
    <Section
      title={goal.name}
      description={`${progressText(goal)}${goal.baseline_note ? ` · ${goal.baseline_note}` : ""}`}
      actions={
        <>
          {(goal.id === "scripts_published" || goal.id === "weekly_script") && (
            <a className="button button-secondary button-small" href="/scripts">
              Open library
            </a>
          )}
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
      <div className="toolbar">
        <label className="select-field">
          <span className="sr-only">Skill assignment</span>
          <select value={skillId} onChange={(event) => void assignSkill(event.target.value)}>
            <option value="">Unassigned skill</option>
            {props.skills.map((skill) => (
              <option value={skill.id} key={skill.id}>
                {skill.name}
              </option>
            ))}
          </select>
        </label>
        {goal.skill_name ? <span className="toolbar-count">Skill: {goal.skill_name}</span> : null}
      </div>

      {props.source ? (
        <div className="panel review-card">
          <div className="activity-head">
            <strong>Live source: {props.source.name}</strong>
            {props.source.last_status === "stale" ? <Tag>Stale</Tag> : <Tag tone="accent">Live</Tag>}
          </div>
          <p className="muted">
            Path: <code>{props.source.path}</code>
          </p>
          <p className="muted">
            Published: {Number(observed.published ?? 0)} · Drafts: {Number(observed.drafts ?? 0)} · Unknown:{" "}
            {Number(observed.unknown ?? 0)} · Excluded: {Number(observed.excluded ?? 0)} of{" "}
            {Number(observed.candidates ?? 0)} files
            {props.source.last_sync_at ? ` · Last sync: ${formatDateTime(props.source.last_sync_at)}` : " · Never synced"}
          </p>
          {props.source.last_error ? <p className="muted">Note: {props.source.last_error}</p> : null}
          {goal.progress.disagreement ? <p className="muted">Reconciliation required: {goal.progress.disagreement}</p> : null}
          <div className="toolbar">
            <button className="button button-secondary button-small" onClick={() => void syncSource()} disabled={syncing}>
              {syncing ? "Syncing…" : "Refresh from source"}
            </button>
          </div>
        </div>
      ) : null}

      {(goal.id === "scripts_published" || goal.id === "weekly_script") && (
        <ScriptGoalExtras goalId={goal.id} />
      )}

      <div className="stat-strip">
        <Stat label="Progress" value={progressText(goal)} />
        <Stat label="Items in pipeline" value={Object.values(goal.progress.pipeline).reduce((a, b) => a + b, 0)} />
        <Stat label="Next milestone" value={goal.progress.next_milestone ?? "—"} />
      </div>
      {goal.progress.disagreement ? (
        <p className="notice notice-warning">Reconciliation required: {goal.progress.disagreement}</p>
      ) : null}
      {goal.progress.live_stale ? (
        <p className="notice notice-warning">Source data is stale — showing the last known observation. Sync to refresh.</p>
      ) : null}
      <GoalBar goal={goal} />
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

function ScriptGoalExtras(props: { goalId: string }) {
  const status = useApi<import("../types/api").ScriptStatus>("/api/scripts/status");
  const counts = status.data?.counts;
  if (props.goalId === "weekly_script") {
    return (
      <div className="panel review-card">
        <div className="activity-head">
          <strong>Weekly completion evidence</strong>
          {status.data?.status === "stale" ? <Tag>Stale</Tag> : null}
        </div>
        <p className="muted">
          {status.data?.week?.label ?? "Week of —"} · Counts only explicit completions, never file dates.
        </p>
        <div className="toolbar">
          <a className="button button-secondary button-small" href="/scripts">
            Open Scripts library
          </a>
        </div>
      </div>
    );
  }
  return (
    <div className="panel review-card">
      <div className="activity-head">
        <strong>Script inventory</strong>
        {status.data?.status === "stale" ? <Tag>Stale</Tag> : status.data?.status === "never_synced" ? <Tag>Never synced</Tag> : <Tag tone="accent">Live</Tag>}
      </div>
      <p className="muted">
        Discovered: <strong>{counts?.total ?? "—"}</strong> · Completed: <strong>{counts?.completed ?? "—"} / 100</strong>
        {" · "}Ready: {counts?.ready ?? counts?.by_status?.ready ?? 0} · Needs review: {counts?.needs_review ?? 0} · Missing: {counts?.missing ?? 0}
        {status.data?.last_sync_at ? ` · Last sync ${formatDateTime(status.data.last_sync_at)}` : " · Never synced"}
      </p>
      <p className="muted">Existence is inventory; only explicit acceptance counts toward the goal.</p>
      <div className="toolbar">
        <a className="button button-secondary button-small" href="/scripts">
          Open Scripts library
        </a>
        <a className="button button-ghost button-small" href="/scripts?completed=incomplete">
          Needs review
        </a>
      </div>
    </div>
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

// --------------------------------------------------------------- cycles
function CycleSection(props: {
  cycles: import("../types/api").CultivationCycle[];
  goals: CultivationGoal[];
  onChanged: () => void;
}) {
  const toast = useToast();
  const [startDate, setStartDate] = useState("");
  const [focus, setFocus] = useState<string[]>([]);
  const active = props.cycles.find((cycle) => cycle.state === "active") ?? props.cycles[0] ?? null;

  useEffect(() => {
    if (active) setFocus(active.focus_goal_ids);
  }, [active?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!active) return null;

  async function saveSettings() {
    try {
      await api.patch(`/api/cultivation/cycles/${active!.id}`, {
        start_date: startDate || null,
      });
      if (focus.length) await api.put(`/api/cultivation/cycles/${active!.id}/focus`, { goal_ids: focus });
      toast.push("success", "Cycle updated");
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Cycle update failed", errorMessage(caught));
    }
  }

  async function rollover() {
    try {
      await api.post(`/api/cultivation/cycles/${active!.id}/rollover`);
      toast.push("success", "Cycle rolled over — new cycle opened");
      props.onChanged();
    } catch (caught) {
      toast.push("error", "Rollover failed", errorMessage(caught));
    }
  }

  function toggleFocus(id: string) {
    setFocus((current) => (current.includes(id) ? current.filter((goal) => goal !== id) : [...current, id]));
  }

  return (
    <Section
      title="100-day cycles"
      description="What this period focuses on, separate from lifetime totals."
      actions={
        <button className="button button-secondary button-small" onClick={() => void rollover()}>
          Complete cycle & open next
        </button>
      }
    >
      <div className="cultivation-cycle">
        <div className="activity-head">
          <CalendarRange size={14} aria-hidden="true" />
          <strong>
            Cycle {active.number} — {active.name}
          </strong>
          <Tag>{active.state}</Tag>
        </div>
        <p>{active.day.label}</p>
        {active.day.mode === "snapshot" && active.snapshot_note ? <p className="muted">{active.snapshot_note}</p> : null}
        {active.progress.window ? (
          <p className="muted">
            Window: {active.progress.window.from} → {active.progress.window.to}
          </p>
        ) : (
          <p className="muted">No attribution window — set a start date to measure completions within this cycle.</p>
        )}
        {(active.progress.focus ?? []).map((entry) => (
          <p key={entry.goal_id} className="row-line">
            {entry.goal_name}:{" "}
            {entry.completions_in_window == null ? (
              <span className="muted">lifetime {entry.current ?? "unknown"}</span>
            ) : (
              <span>
                {entry.completions_in_window} completed · {entry.started_in_window ?? 0} started this cycle · lifetime{" "}
                {entry.current ?? "unknown"}
              </span>
            )}
          </p>
        ))}
      </div>
      <div className="form-grid two">
        <label className="field">
          <span>Start date (enables day count)</span>
          <input type="date" value={startDate} placeholder={active.start_date ?? "YYYY-MM-DD"} onChange={(event) => setStartDate(event.target.value)} />
        </label>
        <div className="field">
          <span>Focus goals</span>
          {(props.goals ?? []).filter((goal) => goal.state === "active").map((goal) => (
            <label key={goal.id} className="checkbox">
              <input type="checkbox" checked={focus.includes(goal.id)} onChange={() => toggleFocus(goal.id)} /> {goal.name}
            </label>
          ))}
        </div>
      </div>
      <div className="toolbar">
        <button className="button button-primary button-small" onClick={() => void saveSettings()}>
          Save cycle settings
        </button>
      </div>
    </Section>
  );
}

// --------------------------------------------------------------- new goal
function NewGoalModal(props: { skills: Array<{ id: string; name: string }>; onClose: () => void; onCreated: (id: string) => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [target, setTarget] = useState("100");
  const [unit, setUnit] = useState("items");
  const [measurementType, setMeasurementType] = useState("count");
  const [category, setCategory] = useState("general");
  const [skillId, setSkillId] = useState("");
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
        skill_id: skillId || null,
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
        <label className="field">
          <span>Skill (optional)</span>
          <select value={skillId} onChange={(event) => setSkillId(event.target.value)}>
            <option value="">Unassigned</option>
            {props.skills.map((skill) => (
              <option value={skill.id} key={skill.id}>
                {skill.name}
              </option>
            ))}
          </select>
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
