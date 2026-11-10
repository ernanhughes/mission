import { useState } from "react";
import { Link } from "react-router-dom";
import { NotebookPen } from "lucide-react";
import { errorMessage } from "../../api/client";
import { useApi } from "../../api/useApi";
import { useToast } from "../../components/Toast";
import type { Application } from "../../types/api";
import { WORKBENCH_APP_ID, ensureWorkbenchOpen } from "./ensureWorkbenchOpen";

type SidebarState = "running" | "stopped" | "starting" | "unavailable";

function toSidebarState(app: Application | null, starting: boolean): SidebarState {
  if (starting) return "starting";
  if (!app) return "unavailable";
  switch (app.status.state) {
    case "running":
      return "running";
    case "stopped":
    case "not_checked":
      return "stopped";
    default:
      return "unavailable";
  }
}

const STATE_LABEL: Record<SidebarState, string> = {
  running: "Running",
  stopped: "Stopped",
  starting: "Starting",
  unavailable: "Unavailable",
};

const DOT_CLASS: Record<SidebarState, string> = {
  running: "status-running",
  stopped: "status-stopped",
  starting: "status-in_progress",
  unavailable: "status-unavailable",
};

export function WorkbenchSidebarAction() {
  const workbench = useApi<Application>(`/api/applications/${WORKBENCH_APP_ID}`, {
    pollMs: 15000,
  });
  const toast = useToast();
  const [starting, setStarting] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const state = toSidebarState(workbench.data, starting);

  async function onClick() {
    if (starting) return;
    setStarting(true);
    setFailure(null);
    if (!starting) toast.push("info", "Starting Workbench…");
    try {
      const url = await ensureWorkbenchOpen();
      toast.push("success", "Workbench ready", url);
      workbench.reload();
    } catch (caught) {
      const message = errorMessage(caught);
      setFailure(message);
      toast.push("error", "Workbench could not start", message);
      workbench.reload();
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="workbench-action-wrap">
      <button
        type="button"
        className="nav-link workbench-action"
        onClick={() => void onClick()}
        disabled={starting}
        aria-label={`Open Workbench (${STATE_LABEL[state]})`}
        title={workbench.data?.status.detail ?? STATE_LABEL[state]}
      >
        <NotebookPen size={16} strokeWidth={1.8} aria-hidden="true" />
        <span className="workbench-copy">
          <span>Open Workbench</span>
          <span className="workbench-sub">
            {starting ? "Starting…" : "Start if needed · Open browser"}
          </span>
        </span>
        <span
          className={`status-dot ${DOT_CLASS[state]}`}
          aria-hidden="true"
          title={STATE_LABEL[state]}
        />
      </button>
      {failure ? (
        <p className="workbench-error" role="alert">
          <span>Workbench could not start: {failure}</span>{" "}
          <Link to="/applications">View logs</Link>
        </p>
      ) : null}
    </div>
  );
}
