import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { apiPath } from "../api/client";
import { useApi } from "../api/useApi";
import {
  EmptyState,
  ErrorState,
  LoadingBlock,
  PageHeader,
  Tag,
} from "../components/ui";
import { timeAgo } from "../lib/format";
import type { SearchResult } from "../types/api";

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const initial = params.get("q") ?? "";
  const [query, setQuery] = useState(initial);
  const [debounced, setDebounced] = useState(initial);
  const [source, setSource] = useState("all");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const next = query.trim();
      setDebounced(next);
      if (next.length >= 2 && params.get("q") !== next) {
        setParams({ q: next }, { replace: true });
      }
    }, 250);
    return () => window.clearTimeout(timer);
    // setParams is stable; including params would restart the timer after URL updates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const search = useApi<SearchResult[]>(
    debounced.length >= 2 ? apiPath("/api/search", { q: debounced, limit: 100 }) : null,
  );
  const results = useMemo(() => {
    const rows = search.data ?? [];
    return source === "all" ? rows : rows.filter((row) => row.source === source);
  }, [search.data, source]);
  const sources = useMemo(
    () => Array.from(new Set((search.data ?? []).map((row) => row.source))).sort(),
    [search.data],
  );

  return (
    <div className="page search-page">
      <PageHeader
        eyebrow="Federated search"
        title="Search everything"
        description="One query across Next research, Work opportunities, CoCoder findings, projects, checkpoints, tasks and decisions."
      />
      <div className="search-hero">
        <Search size={22} aria-hidden="true" />
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search research, jobs, repositories, books, checkpoints…"
          aria-label="Search all sources"
        />
        {query ? (
          <button className="button button-ghost button-small" onClick={() => setQuery("")}>
            Clear
          </button>
        ) : null}
      </div>
      {sources.length ? (
        <div className="search-source-filter">
          <button
            className={source === "all" ? "active" : ""}
            onClick={() => setSource("all")}
          >
            All <span>{search.data?.length ?? 0}</span>
          </button>
          {sources.map((item) => (
            <button
              className={source === item ? "active" : ""}
              key={item}
              onClick={() => setSource(item)}
            >
              {item} <span>{search.data?.filter((row) => row.source === item).length ?? 0}</span>
            </button>
          ))}
        </div>
      ) : null}

      {debounced.length < 2 ? (
        <EmptyState
          title="Search the working context"
          description="Enter at least two characters. Results preserve the source system and open inside the relevant Mission Control workspace."
          icon={<Search size={20} />}
        />
      ) : null}
      {search.loading ? <LoadingBlock label="Searching local sources" compact /> : null}
      {search.error ? <ErrorState message={search.error.message} onRetry={search.reload} /> : null}
      {debounced.length >= 2 && search.data && results.length === 0 ? (
        <EmptyState
          title="No matching records"
          description="Try a broader term or refresh the application integrations."
          icon={<Search size={20} />}
        />
      ) : null}
      {results.length ? (
        <div className="search-results">
          {results.map((result) => (
            <Link className="search-result" to={result.target_path} key={`${result.source}-${result.id}`}>
              <div className="search-result-source">
                <Tag tone={result.source === "Mission Control" ? "default" : "accent"}>
                  {result.source}
                </Tag>
                {result.observed_at ? <span>{timeAgo(result.observed_at)}</span> : null}
              </div>
              <div>
                <strong>{result.title}</strong>
                <p>{result.subtitle || "No additional summary."}</p>
              </div>
              <span className="search-result-arrow">Open →</span>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}
