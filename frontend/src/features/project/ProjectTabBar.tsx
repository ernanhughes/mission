import { useRef } from "react";
import { PROJECT_TABS, type ProjectTabId } from "./projectTabs";

export function ProjectTabBar({
  active,
  onSelect,
  badges,
}: {
  active: ProjectTabId;
  onSelect: (tab: ProjectTabId) => void;
  badges: Partial<Record<ProjectTabId, number | null>>;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft" && event.key !== "Home" && event.key !== "End") return;
    const buttons = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? [],
    );
    if (!buttons.length) return;
    const index = buttons.findIndex((b) => b.getAttribute("aria-selected") === "true");
    event.preventDefault();
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % buttons.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + buttons.length) % buttons.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = buttons.length - 1;
    buttons[next]?.focus();
    buttons[next]?.click();
  }

  return (
    <div
      className="project-tabbar"
      role="tablist"
      aria-label="Project workspace sections"
      ref={listRef}
      onKeyDown={onKeyDown}
    >
      {PROJECT_TABS.map((entry) => {
        const selected = active === entry.id;
        const badge = badges[entry.id];
        return (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`tab-${entry.id}`}
            aria-selected={selected}
            aria-controls={`panel-${entry.id}`}
            tabIndex={selected ? 0 : -1}
            className={`project-tab ${selected ? "is-selected" : ""}`}
            onClick={() => onSelect(entry.id)}
          >
            {entry.label}
            {typeof badge === "number" && badge > 0 ? (
              <span className="project-tab-badge" aria-label={`${badge} items need attention`}>
                {badge > 99 ? "99+" : badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
