import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Sprout, Trophy } from "lucide-react";
import { useApi } from "../../api/useApi";
import type { CultivationHud } from "../../types/api";

function percentOf(progress: CultivationHud["primary"]): number | null {
  if (!progress) return null;
  if (progress.progress.percent == null) return null;
  return Math.min(100, Math.max(0, progress.progress.percent));
}

function currentLabel(progress: NonNullable<CultivationHud["primary"]>): string {
  const detail = progress.progress;
  if (detail.estimate_label) return detail.estimate_label;
  if (detail.current == null) return detail.unknown_reason ?? "Unknown";
  const formatted = Number.isInteger(detail.current) ? `${detail.current}` : detail.current.toFixed(1);
  return `${formatted} / ${detail.target} ${detail.unit}`;
}

export function CultivationHud() {
  const [open, setOpen] = useState(false);
  const hud = useApi<CultivationHud>("/api/cultivation/hud", { pollMs: 60000 });
  const primary = hud.data?.primary ?? null;
  const percent = percentOf(primary);

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
          <strong>{primary ? primary.name : "Cultivation"}</strong>
          <span className="hud-compact-detail">
            {hud.loading && !hud.data
              ? "Loading…"
              : primary
                ? currentLabel(primary)
                : "No pinned goal"}
          </span>
        </span>
        <span className="hud-bar" aria-hidden="true">
          <span style={{ width: `${percent ?? 0}%` }} />
        </span>
        <ChevronDown size={14} aria-hidden="true" className={open ? "hud-chevron-open" : ""} />
      </button>
      {open ? (
        <div className="hud-panel">
          {hud.data?.rank ? (
            <p className="hud-rank">
              <Trophy size={13} aria-hidden="true" /> {hud.data.rank.name}
              <span className="muted"> — {hud.data.rank.concept}</span>
            </p>
          ) : null}
          {(hud.data?.pinned ?? []).map((goal) => (
            <div className="hud-goal" key={goal.id}>
              <div className="hud-goal-head">
                <Link to={`/cultivation?goal=${encodeURIComponent(goal.id)}`}>{goal.name}</Link>
                {goal.privacy === "private" ? <span className="tag">Private</span> : null}
                {goal.progress.achieved ? <span className="tag tag-accent">Achieved</span> : null}
              </div>
              <div className="hud-goal-progress">
                <span className="hud-bar" aria-hidden="true">
                  <span style={{ width: `${percentOf(goal) ?? 0}%` }} />
                </span>
                <span className="muted">{currentLabel(goal)}</span>
              </div>
            </div>
          ))}
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
