import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Bot,
  MessageSquare,
  RefreshCw,
  Send,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { api, errorMessage } from "../../api/client";
import { formatDateTime, titleCase, truncate } from "../../lib/format";
import type {
  IntegrationRecord,
  ResearchChatSession,
  ResearchChatSessionSummary,
  ResearchModelCatalogue,
} from "../../types/api";
import { MarkdownText } from "./MarkdownText";

const SUGGESTIONS = [
  "Explain the core research mechanism.",
  "What is the evidence for self-improvement?",
  "How could we test this in our existing systems?",
  "What would falsify the opportunity?",
];

function requestKey(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `turn-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function sessionPath(sessionId: string) {
  return `/api/research/sessions/${sessionId}`;
}

export function ResearchChatPanel({
  record,
  onClose,
}: {
  record: IntegrationRecord;
  onClose: () => void;
}) {
  const [catalogue, setCatalogue] = useState<ResearchModelCatalogue | null>(null);
  const [catalogueLoading, setCatalogueLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState("");
  const [sessions, setSessions] = useState<ResearchChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<ResearchChatSession | null>(null);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  async function loadCatalogue() {
    setCatalogueLoading(true);
    try {
      const result = await api.get<ResearchModelCatalogue>("/api/research/models");
      setCatalogue(result);
      setSelectedModel((current) => {
        if (current && result.models.some((model) => model.id === current)) return current;
        if (result.selected && result.models.some((model) => model.id === result.selected)) {
          return result.selected;
        }
        return result.models[0]?.id ?? "";
      });
    } catch (caught) {
      setCatalogue(null);
      setError(errorMessage(caught));
    } finally {
      setCatalogueLoading(false);
    }
  }

  async function loadSessions(selectFirst: boolean) {
    try {
      const result = await api.get<ResearchChatSessionSummary[]>(
        `/api/research/opportunities/${record.id}/sessions`,
      );
      setSessions(result);
      if (selectFirst) {
        setActiveSessionId((current) => current ?? result[0]?.id ?? null);
      }
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  useEffect(() => {
    void loadCatalogue();
    void loadSessions(true);
    // The record is the identity of this panel; a different opportunity must not
    // inherit the previous conversation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record.id]);

  useEffect(() => {
    if (!activeSessionId) {
      setSession(null);
      return;
    }
    const controller = new AbortController();
    setSessionLoading(true);
    setError(null);
    api
      .get<ResearchChatSession>(sessionPath(activeSessionId), controller.signal)
      .then((result) => {
        setSession(result);
        setSelectedModel(result.model_id);
      })
      .catch((caught) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(errorMessage(caught));
      })
      .finally(() => {
        if (!controller.signal.aborted) setSessionLoading(false);
      });
    return () => controller.abort();
  }, [activeSessionId]);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [session?.messages.length, sending, sessionLoading]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const localModels = catalogue?.models ?? [];
  const available = Boolean(catalogue?.available && localModels.length);
  const canSend = Boolean(
    message.trim() &&
      selectedModel &&
      available &&
      !sending &&
      !sessionLoading &&
      (!session || session.model_id === selectedModel),
  );
  const existingSession = Boolean(session);
  const pickerValue = activeSessionId ?? "new";

  const modelOptions = useMemo(() => {
    if (existingSession && session) {
      return [
        {
          id: session.model_id,
          label: `${session.model_id} (conversation model)`,
        },
      ];
    }
    return localModels.map((model) => ({
      id: model.id,
      label: model.configured ? `${model.label} (configured)` : model.label,
    }));
  }, [existingSession, session, localModels]);

  function startNewConversation() {
    setActiveSessionId(null);
    setSession(null);
    setMessage("");
    setError(null);
    setSelectedModel((current) => {
      if (catalogue?.selected && localModels.some((model) => model.id === catalogue.selected)) {
        return catalogue.selected;
      }
      if (localModels.some((model) => model.id === current)) return current;
      return localModels[0]?.id ?? "";
    });
  }

  async function sendMessage() {
    const text = message.trim();
    if (!text || !selectedModel || sending) return;
    setSending(true);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    let currentSession = session;
    try {
      if (!currentSession) {
        currentSession = await api.post<ResearchChatSession>(
          `/api/research/opportunities/${record.id}/sessions`,
          { model_id: selectedModel, model_route: catalogue?.route ?? "configured-local-openai" },
          controller.signal,
        );
        setSession(currentSession);
        setActiveSessionId(currentSession.id);
      }
      const updated = await api.post<ResearchChatSession>(
        `${sessionPath(currentSession.id)}/messages`,
        { content: text, request_key: requestKey() },
        controller.signal,
      );
      setSession(updated);
      setMessage("");
      await loadSessions(false);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        setError(
          "Stopped waiting. Reopen the conversation to see whether a response was retained; no partial answer is presented.",
        );
      } else {
        setError(errorMessage(caught));
      }
      if (currentSession) {
        try {
          const retained = await api.get<ResearchChatSession>(sessionPath(currentSession.id));
          setSession(retained);
          await loadSessions(false);
        } catch {
          // The original error remains the useful diagnostic.
        }
      }
    } finally {
      setSending(false);
      abortRef.current = null;
    }
  }

  async function refreshContext() {
    if (!session) return;
    setRefreshing(true);
    setError(null);
    try {
      const updated = await api.post<ResearchChatSession>(
        `${sessionPath(session.id)}/refresh-context`,
      );
      setSession(updated);
      await loadSessions(false);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setRefreshing(false);
    }
  }

  function useSuggestion(suggestion: string) {
    setMessage(suggestion);
  }

  return (
    <div
      className="research-chat-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        className="research-chat-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Research conversation"
      >
        <header className="research-chat-head">
          <div>
            <span className="eyebrow">Research conversation</span>
            <h2>{record.title}</h2>
            <p className="muted small">
              {titleCase(String(record.data?.mode || record.resource_type))} ·{" "}
              {(record.data?.items as unknown[] | undefined)?.length ?? 0} source item(s) ·{" "}
              {record.external_id}
            </p>
            <p className="muted small research-chat-summary">
              {truncate(record.summary, 280)}
            </p>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close research conversation"
          >
            <X size={17} />
          </button>
        </header>

        <div className="research-chat-controls">
          <label className="field">
            <span>Model</span>
            <select
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              disabled={existingSession || !modelOptions.length || sending}
              aria-label="Research chat model"
            >
              {!modelOptions.length ? (
                <option value="">No local model available</option>
              ) : null}
              {modelOptions.map((model) => (
                <option value={model.id} key={model.id}>
                  {model.label}
                </option>
              ))}
            </select>
          </label>
          <div className="research-chat-route">
            <span
              className={`local-model-badge ${
                catalogue?.local && catalogue.available ? "local" : "blocked"
              }`}
            >
              {catalogueLoading
                ? "Checking local model…"
                : catalogue?.local
                  ? catalogue.available
                    ? "Local inference"
                    : "Local unavailable"
                  : "Not local"}
            </span>
            {catalogue?.endpoint ? <span className="muted small">{catalogue.endpoint}</span> : null}
            <button
              className="button button-ghost button-small"
              onClick={() => void loadCatalogue()}
              disabled={catalogueLoading}
              type="button"
            >
              <RefreshCw size={13} className={catalogueLoading ? "spin" : ""} /> Check
            </button>
          </div>
        </div>

        {catalogue && !catalogue.available ? (
          <div className="research-chat-notice warn">
            <AlertTriangle size={15} />
            <div>
              <strong>No verified local model</strong>
              <p>{catalogue.detail}</p>
              <Link className="text-link" to="/settings" onClick={onClose}>
                Configure local inference
              </Link>
            </div>
          </div>
        ) : null}

        {catalogue?.available && !catalogue.local ? (
          <div className="research-chat-notice warn">
            <AlertTriangle size={15} />
            <div>
              <strong>Local-only route required</strong>
              <p>
                This endpoint is not loopback. Research chat will not send the selected
                opportunity to a remote provider.
              </p>
            </div>
          </div>
        ) : null}

        <div className="research-chat-session-bar">
          <label className="field">
            <span>Conversation</span>
            <select
              value={pickerValue}
              onChange={(event) => {
                const value = event.target.value;
                setActiveSessionId(value === "new" ? null : value);
                if (value === "new") startNewConversation();
              }}
              aria-label="Research conversation history"
            >
              <option value="new">New conversation</option>
              {sessions.map((item) => (
                <option value={item.id} key={item.id}>
                  {truncate(item.last_message || item.opportunity_title, 58)} ·{" "}
                  {formatDateTime(item.updated_at)}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button button-secondary button-small"
            onClick={startNewConversation}
            type="button"
          >
            <MessageSquare size={14} /> New
          </button>
        </div>

        {session?.context_stale ? (
          <div className="research-chat-notice stale">
            <AlertTriangle size={15} />
            <div>
              <strong>Source opportunity has changed</strong>
              <p>{session.freshness_notice}</p>
              <button
                className="button button-secondary button-small"
                onClick={() => void refreshContext()}
                disabled={refreshing}
                type="button"
              >
                <RefreshCw size={13} className={refreshing ? "spin" : ""} />{" "}
                {refreshing ? "Refreshing…" : "Refresh context explicitly"}
              </button>
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="research-chat-notice error" role="alert">
            <AlertTriangle size={15} />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="research-chat-messages" ref={scrollRef} aria-live="polite">
          {sessionLoading ? <p className="muted small">Loading conversation…</p> : null}
          {!sessionLoading && !session?.messages.length ? (
            <div className="research-chat-empty">
              <span className="research-chat-empty-icon">
                <Sparkles size={20} />
              </span>
              <h3>Interrogate this research</h3>
              <p>
                The conversation starts with a frozen, evidence-grounded snapshot of this
                opportunity. Nothing is sent to a model until you submit a message.
              </p>
              <div className="research-chat-suggestions">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    className="chat-suggestion"
                    onClick={() => useSuggestion(suggestion)}
                    type="button"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {session?.messages.map((item) => (
            <div className={`chat-message chat-${item.role}`} key={item.id}>
              <div className="chat-message-label">
                <span>{item.role === "user" ? "You" : "AI assistant"}</span>
                <span>{formatDateTime(item.created_at)}</span>
              </div>
              {item.role === "assistant" ? (
                item.status === "completed" ? (
                  <MarkdownText content={item.content} />
                ) : item.status === "pending" ? (
                  <p className="muted small">
                    <Bot size={14} /> Waiting for the local model…
                  </p>
                ) : (
                  <div className="chat-failure">
                    <strong>Model response failed</strong>
                    <p>{item.error || "No response was recorded."}</p>
                  </div>
                )
              ) : (
                <p className="chat-user-text">{item.content}</p>
              )}
              {item.role === "assistant" && item.status === "completed" ? (
                <div className="chat-message-meta">
                  <span>{item.model || session?.model_id}</span>
                  <span>{item.provider}</span>
                  <span>{item.metadata?.local ? "local route" : "route not confirmed local"}</span>
                  {item.metadata?.latency_ms ? (
                    <span>{String(item.metadata.latency_ms)} ms</span>
                  ) : null}
                </div>
              ) : null}
            </div>
          ))}
          {sending ? (
            <div className="chat-thinking">
              <span className="chat-thinking-dot" />
              <span>Model is thinking…</span>
              <button
                className="button button-ghost button-small"
                onClick={() => abortRef.current?.abort()}
                type="button"
              >
                <Square size={13} /> Stop
              </button>
            </div>
          ) : null}
        </div>

        <div className="research-chat-composer">
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                event.preventDefault();
                void sendMessage();
              }
            }}
            placeholder="Ask about this research…"
            aria-label="Message the research model"
            rows={3}
            disabled={!available || sending}
          />
          <div className="research-chat-composer-actions">
            <span className="muted small">Ctrl+Enter to send · conversation stays with this opportunity</span>
            <button
              className="button button-primary button-small"
              onClick={() => void sendMessage()}
              disabled={!canSend}
              type="button"
            >
              <Send size={14} /> {sending ? "Sending…" : "Send"}
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
