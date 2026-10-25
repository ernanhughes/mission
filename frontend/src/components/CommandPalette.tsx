import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Command, CornerDownLeft, RefreshCw, Search } from "lucide-react";
import { api, apiPath, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "./Toast";
import type { Integration, SearchResult } from "../types/api";

type CommandItem = {
  id: string;
  label: string;
  hint: string;
  path?: string;
  refresh?: string;
};

const commands: CommandItem[] = [
  { id: "today", label: "Today", hint: "Daily workspace", path: "/" },
  { id: "inbox", label: "Unified inbox", hint: "Awaiting attention across engines", path: "/inbox" },
  { id: "search", label: "Search everything", hint: "Research, Work, CoCoder, projects", path: "/search" },
  { id: "next", label: "Next workspace", hint: "Candidates, evidence, recommendations", path: "/next" },
  { id: "work", label: "Work workspace", hint: "Opportunities and qualification", path: "/work" },
  { id: "cocoder", label: "CoCoder workspace", hint: "Assessments and findings", path: "/cocoder" },
  { id: "workflows", label: "Experiment workflows", hint: "Next → approval → Worker → CoCoder → decision", path: "/workflows" },
  { id: "writer", label: "Writer editing", hint: "Readability reports, findings and stale evidence", path: "/writer" },
  { id: "books", label: "Books", hint: "Language, Inference, Math", path: "/books" },
  { id: "projects", label: "Projects", hint: "All bodies of work", path: "/projects" },
  { id: "project-math", label: "Math project", hint: "Book, proof obligations and shared context", path: "/projects/math" },
  { id: "project-language", label: "Language project", hint: "Book and shared context", path: "/projects/language" },
  { id: "project-inference", label: "Inference project", hint: "Book and shared context", path: "/projects/inference" },
  { id: "applications", label: "Applications", hint: "Registry and launches", path: "/applications" },
  { id: "integrations", label: "Integrations", hint: "Connections, diagnostics and actions", path: "/integrations" },
  { id: "activity", label: "Activity", hint: "Decisions, evidence, failures", path: "/activity" },
  { id: "settings", label: "Settings", hint: "Local configuration", path: "/settings" },
  { id: "refresh-next", label: "Refresh Next data", hint: "Read-only live source refresh", refresh: "next" },
  { id: "refresh-work", label: "Refresh Work opportunities", hint: "Read-only CLI refresh", refresh: "work" },
  { id: "refresh-cocoder", label: "Refresh CoCoder findings", hint: "Read the latest review artifacts", refresh: "cocoder" },
];

function sourceForRecord(target: string): string {
  if (target.startsWith("/next")) return "Next";
  if (target.startsWith("/work")) return "Work";
  if (target.startsWith("/cocoder")) return "CoCoder";
  if (target.startsWith("/writer")) return "Writer";
  return "Mission Control";
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const search = useApi<SearchResult[]>(
    debounced.trim().length >= 2
      ? apiPath("/api/search", { q: debounced.trim(), limit: 12 })
      : null,
  );
  const integrations = useApi<Integration[]>(open ? "/api/integrations" : null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setDebounced("");
      window.setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query), 220);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const availableCommands = useMemo(
    () =>
      commands.filter((command) => {
        if (!command.refresh) return true;
        const integration = integrations.data?.find(
          (item) => item.application_id === command.refresh,
        );
        return Boolean(integration?.enabled && integration.available);
      }),
    [integrations.data],
  );

  const filteredCommands = useMemo(() => {
    const needle = query.toLocaleLowerCase().trim();
    if (!needle) return availableCommands.slice(0, 9);
    return availableCommands.filter(
      (command) =>
        command.label.toLocaleLowerCase().includes(needle) ||
        command.hint.toLocaleLowerCase().includes(needle),
    );
  }, [query, availableCommands]);

  if (!open) return null;

  async function refresh(applicationId: string) {
    try {
      await api.post(`/api/integrations/${applicationId}/refresh`);
      toast.push("success", `${applicationId} integration refreshed`);
      onClose();
    } catch (caught) {
      toast.push("error", "Integration refresh failed", errorMessage(caught));
    }
  }

  return (
    <div className="palette-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <div className="palette-search">
          <Search size={18} aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search research, work, code, projects, or run a command…"
            aria-label="Search or run a command"
          />
          <kbd>Esc</kbd>
        </div>
        <div className="palette-body">
          {filteredCommands.length ? (
            <div className="palette-group">
              <span className="palette-caption">
                <Command size={12} /> Commands
              </span>
              {filteredCommands.map((command) => (
                <button
                  className="palette-item"
                  key={command.id}
                  onClick={() => {
                    if (command.path) navigate(command.path);
                    if (command.refresh) void refresh(command.refresh);
                    onClose();
                  }}
                >
                  <span className="palette-item-main">
                    <strong>{command.label}</strong>
                    <span>{command.hint}</span>
                  </span>
                  {command.refresh ? <RefreshCw size={14} /> : <CornerDownLeft size={14} />}
                </button>
              ))}
            </div>
          ) : null}
          {debounced.trim().length >= 2 ? (
            <div className="palette-group">
              <span className="palette-caption">Search results</span>
              {search.loading ? <span className="muted small">Searching…</span> : null}
              {search.error ? <span className="warn-text small">{search.error.message}</span> : null}
              {search.data?.map((result) => (
                <button
                  className="palette-item"
                  key={result.id}
                  onClick={() => {
                    navigate(result.target_path);
                    onClose();
                  }}
                >
                  <span className="palette-item-main">
                    <strong>{result.title}</strong>
                    <span>
                      {sourceForRecord(result.target_path)} · {result.subtitle}
                    </span>
                  </span>
                  <CornerDownLeft size={14} />
                </button>
              ))}
              {!search.loading && search.data?.length === 0 ? (
                <span className="muted small">No matching resources.</span>
              ) : null}
            </div>
          ) : null}
        </div>
        <footer className="palette-footer">
          <span><kbd>↵</kbd> open</span>
          <span><kbd>Esc</kbd> close</span>
        </footer>
      </div>
    </div>
  );
}
