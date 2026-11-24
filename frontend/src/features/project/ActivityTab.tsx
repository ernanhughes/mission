import { useMemo, useState } from "react";
import { EmptyState, Section } from "../../components/ui";
import { activityLabel, timeAgo, titleCase, truncate } from "../../lib/format";
import { ProvenanceBadge } from "../../components/ui";
import type { ProjectDetail } from "../../types/api";

export function ActivityTab({ data }: { data: ProjectDetail }) {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [provenanceFilter, setProvenanceFilter] = useState("ALL");
  const [visible, setVisible] = useState(50);

  const types = useMemo(
    () => [...new Set((data.activity ?? []).map((e) => e.type))].sort(),
    [data.activity],
  );
  const provenances = useMemo(
    () => [...new Set((data.activity ?? []).map((e) => e.provenance))].sort(),
    [data.activity],
  );

  const needle = query.trim().toLowerCase();
  const filtered = useMemo(() => {
    const sorted = [...(data.activity ?? [])].sort((a, b) =>
      a.occurred_at < b.occurred_at ? 1 : -1,
    );
    return sorted.filter((event) => {
      if (typeFilter !== "ALL" && event.type !== typeFilter) return false;
      if (provenanceFilter !== "ALL" && event.provenance !== provenanceFilter) return false;
      if (needle) {
        const hay = `${event.title} ${event.detail ?? ""} ${event.type}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [data.activity, typeFilter, provenanceFilter, needle]);

  return (
    <Section
      title="Activity"
      description="Project-scoped history with provenance. Newest first."
    >
      <div className="inline-form" role="search">
        <label className="muted small">
          Search{" "}
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setVisible(50);
            }}
            placeholder="title, detail or type"
            aria-label="Search activity"
            size={28}
          />
        </label>
        <label className="muted small">
          Type{" "}
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setVisible(50);
            }}
            aria-label="Filter by event type"
          >
            <option value="ALL">All ({data.activity.length})</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {activityLabel(t)}
              </option>
            ))}
          </select>
        </label>
        <label className="muted small">
          Provenance{" "}
          <select
            value={provenanceFilter}
            onChange={(e) => {
              setProvenanceFilter(e.target.value);
              setVisible(50);
            }}
            aria-label="Filter by provenance"
          >
            <option value="ALL">All</option>
            {provenances.map((p) => (
              <option key={p} value={p}>
                {titleCase(p)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted small">
        {filtered.length} of {data.activity.length} events · newest first.
      </p>
      {filtered.length ? (
        <ul className="activity-feed">
          {filtered.slice(0, visible).map((event) => (
            <li key={event.id}>
              <span className={`activity-marker type-${event.provenance}`} aria-hidden="true" />
              <div>
                <div className="activity-head">
                  <strong>{event.title}</strong>
                  <span className="activity-type">{activityLabel(event.type)}</span>
                </div>
                <span className="activity-meta">
                  {timeAgo(event.occurred_at)} · <ProvenanceBadge value={event.provenance} />
                </span>
                {event.detail ? <p className="activity-detail">{truncate(event.detail, 280)}</p> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          title="No activity matches these filters"
          description="Broaden the search. An empty result is not evidence of inactivity — check the filters."
        />
      )}
      {filtered.length > visible ? (
        <button className="button button-secondary button-small" onClick={() => setVisible((v) => v + 50)}>
          Show more ({filtered.length - visible} remaining)
        </button>
      ) : null}
    </Section>
  );
}
