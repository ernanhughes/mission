import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Bot, X } from "lucide-react";
import type { ProjectDetail, ProjectGitLink } from "../../types/api";

export type StephanieHostContext = {
  schema_version: "stephanie.context.v1";
  event_type: "stephanie.open";
  event_id: string;
  correlation_id: string;
  application: "mission";
  context_type: "repository";
  subject: string;
  revision: string | null;
  view: string;
  document_state: "not_applicable";
  requested_mode: "generate_prompt";
};

type StephaniePanelApi = {
  isOpen: boolean;
  context: StephanieHostContext | null;
  openStephanie: (context?: StephanieHostContext | null) => void;
  updateStephanieContext: (context: StephanieHostContext | null) => void;
  closeStephanie: () => void;
};

const StephaniePanelContext = createContext<StephaniePanelApi | null>(null);
const SIS_URL = ((import.meta.env.VITE_STEPHANIE_URL as string | undefined) ?? "http://127.0.0.1:8766").replace(/\/+$/, "");

export function makeStephanieContext(subject: string, revision: string | null, view: string): StephanieHostContext {
  return {
    schema_version: "stephanie.context.v1", event_type: "stephanie.open",
    event_id: crypto.randomUUID(), correlation_id: crypto.randomUUID(),
    application: "mission", context_type: "repository", subject, revision,
    view, document_state: "not_applicable", requested_mode: "generate_prompt",
  };
}

export function contextForMissionProject(project: Pick<ProjectDetail, "id" | "repositories">,
  links: ProjectGitLink[]): StephanieHostContext {
  const matches=links.filter((link) => project.repositories.some((repo) => repo.id === link.repository_id));
  const primary=matches.find((link) => link.role === "primary") ?? matches[0];
  const repository=project.repositories.find((repo) => repo.role === "primary") ?? project.repositories[0];
  return makeStephanieContext(project.id, primary?.head_sha ?? repository?.commit_hash ?? null, "project-detail");
}

export function StephaniePanelProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [context, setContext] = useState<StephanieHostContext | null>(null);
  const [frameReady, setFrameReady] = useState(false);
  const [frameLoadCount, setFrameLoadCount] = useState(0);
  const frame = useRef<HTMLIFrameElement>(null);
  const openStephanie = useCallback((next?: StephanieHostContext | null) => {
    setContext(next ?? null);
    setIsOpen(true);
  }, []);
  const updateStephanieContext = useCallback((next: StephanieHostContext | null) => setContext(next), []);
  const closeStephanie = useCallback(() => {
    setIsOpen(false);
    setContext(null);
    setFrameReady(false);
  }, []);
  useEffect(() => {
    if (!isOpen || !frameReady || !context) return;
    frame.current?.contentWindow?.postMessage(context, new URL(SIS_URL).origin);
  }, [isOpen, frameReady, frameLoadCount, context]);
  const value = useMemo(() => ({ isOpen, context, openStephanie, updateStephanieContext, closeStephanie }),
    [isOpen, context, openStephanie, updateStephanieContext, closeStephanie]);
  return <StephaniePanelContext.Provider value={value}>
    {children}
    {isOpen ? <>
      <button className="stephanie-panel-backdrop" aria-label="Close Stephanie panel" onClick={closeStephanie} />
      <aside className="stephanie-panel" aria-label="Stephanie contextual assistant">
        <header className="stephanie-panel-header"><div><Bot size={19} /><strong>Stephanie</strong><span>Generate prompt</span></div>
          <button className="icon-button" aria-label="Close Stephanie" onClick={closeStephanie}><X size={18} /></button></header>
        <iframe ref={frame} title="Stephanie prompt generator" allow="clipboard-write" src={`${SIS_URL}/stephanie`} onLoad={() => {
          setFrameReady(true);
          setFrameLoadCount((count) => count + 1);
        }} />
      </aside>
    </> : null}
  </StephaniePanelContext.Provider>;
}

export function useStephaniePanel(): StephaniePanelApi {
  const value = useContext(StephaniePanelContext);
  if (!value) throw new Error("useStephaniePanel must be used inside StephaniePanelProvider");
  return value;
}
