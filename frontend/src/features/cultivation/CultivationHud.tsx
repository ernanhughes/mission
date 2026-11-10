import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Sprout, Trophy } from "lucide-react";
import { useApi } from "../../api/useApi";
import type { CultivationHud, CultivationHudGoal, CultivationProgress } from "../../types/api";
import { barPercent, barState, currentLabel } from "./progress";

function GoalBar(props: { progress: CultivationProgress; block?: boolean }) {
  return (
    <span
      className={props.block ? "hud-bar hud-bar-block" : "hud-bar"}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(barPercent(props.progress))}
      aria-label={currentLabel(props.progress)}
      data-state={barState(props.progress)}
    >
      <span style={{ width: `${barPercent(props.progress)}%` }} />
    </span>
  );
}

function HudGoalRow(props: { goal: { id: string; name: string; privacy?: string | null; progress: CultivationProgress } }) {
  const { goal } = props;
  return (
    <div className="hud-goal">
      <div className="hud-goal-head">
        <Link to={`/cultivation?goal=${encodeURIComponent(goal.id)}`}>{goal.name}</Link>
        {goal.privacy === "private" ? <span className="tag">Private</span> : null}
        {goal.progress.achieved ? <span className="tag tag-accent">Achieved</span> : null}
      </div>
      <div className="hud-goal-progress">
        <GoalBar progress={goal.progress} />
        <span className="muted">{currentLabel(goal.progress)}</span>
      </div>
    </div>
  );
}

export function CultivationHud() {
  const [open, setOpen] = useState(false);
  const hud = useApi<CultivationHud>("/api/cultivation/hud", { pollMs: 60000 });
  const primary = hud.data?.primary ?? null;
  const second = (hud.data?.pinned ?? []).find((goal) => primary == null || goal.id !== primary.id) ?? null;
  const skills = hud.data?.pinned_skills ?? [];
  const cycle = hud.data?.cycle ?? null;

  return (
    <div className="cultivation-hud" aria-label="Cultivation progress">
      <button
        className="hud-compact"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-label={primary ? `Path to ${primary.name}` : "Cultivation"}
        title={primary ? `Path to ${primary.name}` : "Cultivation"}
      >
        <Sprout size={15} aria-hidden="true" />
        <span className="hud-compact-copy">
          {cycle ? <span className="hud-cycle">{cycle.day.label}</span> : null}
          <strong>{primary ? primary.name : "Cultivation"}</strong>
          <span className="hud-compact-detail">
            {hud.loading && !hud.data ? "Loading…" : primary ? currentLabel(primary.progress) : "No pinned goal"}
          </span>
          {second ? <span className="hud-compact-detail">{second.name}: {currentLabel(second.progress)}</span> : null}
        </span>
        {primary ? <GoalBar progress={primary.progress} /> : null}
        <ChevronDown size={14} aria-hidden="true" className={open ? "hud-chevron-open" : ""} />
      </button>
      {open ? (
        <div className="hud-panel">
          {cycle ? (
            <p className="hud-rank">
              <span className="hud-cycle">{cycle.day.label}</span>
              {cycle.day.mode === "snapshot" && cycle.snapshot_note ? (
                <span className="muted"> — reported position</span>
              ) : null}
            </p>
          ) : null}
          {skills.length > 0 ? (
            skills.map((skill) => (
              <div key={skill.id}>
                <span className="hud-skill-name">{skill.name}</span>
                {skill.goals.slice(0, 4).map((goal) => (
                  <HudGoalRow key={goal.id} goal={goal} />
                ))}
                {skill.goals.length > 4 ? (
                  <span className="muted">+{skill.goals.length - 4} more in {skill.name}</span>
                ) : null}
              </div>
            ))
          ) : (
            (hud.data?.pinned ?? []).map((goal) => <HudGoalRow key={goal.id} goal={goal} />)
          )}
          {hud.data?.rank ? (
            <p className="hud-rank">
              <Trophy size={13} aria-hidden="true" /> {hud.data.rank.name}
              <span className="muted"> — {hud.data.rank.concept}</span>
            </p>
          ) : null}
          {(hud.data?.recent_completions ?? []).length > 0 ? (
            <div className="hud-recent">
              <span className="eyebrow">Recent completions</span>
              <ul>
                {(hud.data?.recent_completions ?? []).slice(0, 5).map((event) => (
                  <li key={event.id}>{event.item_title ?? event.note}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <Link className="button button-secondary button-small" to="/cultivation" onClick={() => setOpen(false)}>
            Open cultivation
          </Link>
        </div>
      ) : null}
    </div>
  );
}
