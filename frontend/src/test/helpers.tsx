import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { ToastProvider } from "../components/Toast";

export type ApiCall = {
  path: string;
  method: string;
  body: unknown;
};

export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function apiError(status: number, message: string, code = "request_failed", detail?: unknown): Response {
  return json({ error: { code, message, detail: detail ?? null } }, status);
}

type Handler = (call: ApiCall) => Response | Promise<Response>;

export function mockFetch(handler: Handler): ApiCall[] {
  const calls: ApiCall[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const path = new URL(rawUrl, "http://mission-control.local").pathname;
      let body: unknown = undefined;
      if (typeof init?.body === "string") {
        try {
          body = JSON.parse(init.body);
        } catch {
          body = init.body;
        }
      }
      const call: ApiCall = { path, method: (init?.method ?? "GET").toUpperCase(), body };
      calls.push(call);
      return handler(call);
    }),
  );
  return calls;
}

export function renderRoute(ui: ReactElement, route = "/") {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </ToastProvider>,
  );
}
