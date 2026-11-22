import { useEffect, useState } from "react";
import { ExternalLink, FolderOpen, Globe, Play, Square } from "lucide-react";
import { api, errorMessage } from "../api/client";
import { useApi } from "../api/useApi";
import { useToast } from "../components/Toast";
import { PostsTab } from "../features/websites/PostsTab";
import {
  EmptyState,
  ErrorState,
  KeyValue,
  LoadingBlock,
  PageHeader,
  PathText,
  Section,
  Tag,
} from "../components/ui";
import type { Website } from "../types/api";

export function WebsitesPage() {
  const websites = useApi<Website[]>("/api/websites");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (websites.data?.length && !websites.data.some((site) => site.id === selectedId)) {
      setSelectedId(websites.data[0].id);
    }
  }, [websites.data, selectedId]);

  const selected = (websites.data ?? []).find((site) => site.id === selectedId) ?? null;

  return (
    <div className="page">
      <PageHeader
        eyebrow="Websites and publishing"
        title="Websites"
        description="Website workspaces discovered under the configured websites root. Hugo projects can serve a local preview; nothing launches automatically."
      />

      {websites.loading && !websites.data ? <LoadingBlock label="Loading websites" /> : null}
      {websites.error ? <ErrorState message={websites.error.message} onRetry={websites.reload} /> : null}
      {websites.data && websites.data.length === 0 ? (
        <EmptyState
          title="No website workspaces"
          description="The configured websites root is missing or has no site directories. Check the diagnostics below."
          icon={<Globe size={20} />}
        />
      ) : null}

      {(websites.data ?? []).length > 0 ? (
        <div className="books-layout">
          <aside className="book-selector" aria-label="Websites">
            {(websites.data ?? []).map((site) => (
              <div
                className={`book-selector-item ${selected?.id === site.id ? "active" : ""}`}
                key={site.id}
              >
                <button
                  className="book-selector-main"
                  onClick={() => setSelectedId(site.id)}
                  aria-pressed={selected?.id === site.id}
                  aria-label={`${site.name} — ${site.is_hugo ? "Hugo" : "Non-Hugo"}`}
                >
                  <span className="book-selector-copy">
                    <strong>{site.name}</strong>
                    <span>
                      {site.is_hugo ? "Hugo" : "Static"} ·{" "}
                      {site.running && site.preview_url ? `Running :${site.port}` : site.available ? "Available" : "Unavailable"}
                    </span>
                  </span>
                </button>
                {site.running ? <span className="tag tag-accent">Live</span> : null}
              </div>
            ))}
          </aside>
          <div>{selected ? <WebsiteWorkspace key={selected.id} site={selected} onChanged={websites.reload} /> : null}</div>
        </div>
      ) : null}

      <DiagnosticsSection />

      <Section title="How websites work" className="note-section">
        <p className="muted">
          Discovery is read-only: each immediate subdirectory of the websites root is one
          workspace. Hugo launches use a managed argument-based subprocess bound to
          127.0.0.1 on a distinct port, reused while running and stopped explicitly.
          Drafts are never rendered by default.
        </p>
      </Section>
    </div>
  );
}

function DiagnosticsSection() {
  const diagnostics = useApi<{ root: string; diagnostics: Array<{ path: string; error: string }> }>(
    "/api/websites/diagnostics",
  );
  if (diagnostics.loading && !diagnostics.data) return null;
  if (!diagnostics.data) return null;
  return (
    <Section title="Discovery diagnostics" description={`Root: ${diagnostics.data.root}`}>
      {diagnostics.data.diagnostics.length === 0 ? (
        <p className="muted">Root is available.</p>
      ) : (
        diagnostics.data.diagnostics.map((entry) => (
          <p key={entry.path} className="row-line">
            <code>{entry.path}</code> <span className="muted"> — {entry.error}</span>
          </p>
        ))
      )}
    </Section>
  );
}

function WebsiteWorkspace({ site, onChanged }: { site: Website; onChanged: () => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState<"launch" | "stop" | "open" | null>(null);
  const [tab, setTab] = useState<"overview" | "posts" | "preview">("overview");

  async function launch() {
    setBusy("launch");
    try {
      const result = await api.post<{ url: string; reused: boolean; detail: string | null }>(
        `/api/websites/${site.id}/launch`,
        {},
      );
      toast.push("success", result.reused ? "Reused running preview" : "Hugo preview started", result.url);
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not launch Hugo", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function stop() {
    setBusy("stop");
    try {
      await api.post(`/api/websites/${site.id}/stop`, {});
      toast.push("success", "Hugo preview stopped");
      onChanged();
    } catch (caught) {
      toast.push("error", "Could not stop Hugo", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function openPath() {
    setBusy("open");
    try {
      const result = await api.post<{ detail: string }>(`/api/websites/${site.id}/open-path`, {});
      toast.push("success", "Website folder opened", result.detail ?? undefined);
    } catch (caught) {
      toast.push("error", "Could not open folder", errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="book-workspace">
      <header className="book-workspace-head">
        <div>
          <span className="eyebrow">Website workspace</span>
          <h2>{site.name}</h2>
          <div className="inline-meta">
            <Tag tone={site.is_hugo ? "accent" : undefined}>{site.is_hugo ? "Hugo" : "Non-Hugo"}</Tag>
            {site.running ? <Tag tone="accent">Running</Tag> : null}
            {!site.available ? <Tag>Unavailable</Tag> : null}
          </div>
        </div>
        <div className="button-row">
          <button className="button button-secondary button-small" type="button" onClick={() => void openPath()} disabled={busy !== null}>
            <FolderOpen size={14} /> {busy === "open" ? "Opening…" : "Open folder"}
          </button>
          {site.running && site.preview_url ? (
            <a className="button button-primary button-small" href={site.preview_url} target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> Open preview :{site.port}
            </a>
          ) : null}
        </div>
      </header>

      <div className="toolbar" role="tablist" aria-label="Website workspace views">
        {(
          ["overview", ...(site.content_section ? ["posts" as const] : []), "preview"] as const
        ).map((name) => (
            <button
              key={name}
              role="tab"
              aria-selected={tab === name}
              className={`button button-small ${tab === name ? "button-primary" : "button-ghost"}`}
              onClick={() => setTab(name)}
            >
              {name === "overview" ? "Overview" : name === "posts" ? "Posts" : "Preview"}
            </button>
          ))}
      </div>

      {tab === "posts" && site.content_section ? <PostsTab site={site} /> : null}
      {tab === "overview" ? (
        <section className="panel">
          <span className="eyebrow">Site</span>
          <h3>Details</h3>
          <dl className="kv-list">
            <KeyValue label="Path">
              <PathText>{site.path}</PathText>
            </KeyValue>
            <KeyValue label="Evidence">{site.evidence.join("; ") || "—"}</KeyValue>
            {site.hugo_config ? (
              <KeyValue label="Hugo config">
                <code>{site.hugo_config}</code>
              </KeyValue>
            ) : null}
            {site.content_section ? (
              <KeyValue label="Content section">
                <code>content/{site.content_section}</code>
              </KeyValue>
            ) : null}
            {site.preview_url ? (
              <KeyValue label="Preview">
                <a className="text-link" href={site.preview_url} target="_blank" rel="noreferrer">
                  {site.preview_url} <ExternalLink size={13} />
                </a>
              </KeyValue>
            ) : null}
          </dl>
        </section>
      ) : null}
      {tab === "preview" ? (
        <section className="panel">
          <span className="eyebrow">Hugo preview</span>
          <h3>Local server</h3>
          {!site.is_hugo ? (
            <p className="muted">This site is not a Hugo project, so no Hugo launch is offered.</p>
          ) : !site.hugo_available ? (
            <p className="muted">The Hugo executable was not found on PATH, so launching is unavailable.</p>
          ) : (
            <div className="button-row">
              <button className="button button-primary button-small" type="button" onClick={() => void launch()} disabled={busy !== null || !site.available}>
                <Play size={14} /> {busy === "launch" ? "Starting…" : site.running ? "Rejoin preview" : "Launch Hugo"}
              </button>
              {site.running ? (
                <button className="button button-secondary button-small" type="button" onClick={() => void stop()} disabled={busy !== null}>
                  <Square size={14} /> {busy === "stop" ? "Stopping…" : "Stop"}
                </button>
              ) : null}
            </div>
          )}
          <p className="muted small">
            Binds to 127.0.0.1 on a distinct port. Drafts are not rendered. Use the Posts
            tab for read-only editorial evaluation; nothing here rewrites articles.
          </p>
        </section>
      ) : null}
    </div>
  );
}
