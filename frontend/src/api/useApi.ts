import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./client";

type Options = {
  pollMs?: number;
  enabled?: boolean;
};

export function useApi<T>(path: string | null, options: Options = {}) {
  const { pollMs = 0, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(Boolean(path && enabled));
  const [revision, setRevision] = useState(0);
  const pathRef = useRef(path);
  pathRef.current = path;
  const dataRef = useRef<T | null>(null);
  dataRef.current = data;

  useEffect(() => {
    setData(null);
    setError(null);
    setLoading(Boolean(path && enabled));
  }, [path, enabled]);

  const load = useCallback(
    async (signal?: AbortSignal, quiet = false) => {
      if (!path || !enabled) {
        setLoading(false);
        return;
      }
      if (!quiet && dataRef.current === null) setLoading(true);
      try {
        const result = await api.get<T>(path, signal);
        setData(result);
        setError(null);
      } catch (caught) {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof ApiError ? caught : new ApiError("Request failed"));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [path, enabled],
  );

  useEffect(() => {
    if (!path || !enabled) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    void load(controller.signal, revision > 0);
    let interval: number | undefined;
    if (pollMs > 0) {
      interval = window.setInterval(() => {
        if (!document.hidden) void load(controller.signal, true);
      }, pollMs);
    }
    return () => {
      controller.abort();
      if (interval) window.clearInterval(interval);
    };
  }, [path, enabled, pollMs, revision, load]);

  const reload = useCallback(() => setRevision((value) => value + 1), []);
  return { data, error, loading, reload };
}
