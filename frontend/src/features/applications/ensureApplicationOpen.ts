import { api } from "../../api/client";
import type { EnsureOpenResponse } from "../../types/api";

const inFlight = new Map<string, Promise<EnsureOpenResponse>>();

/**
 * Start a registered application only when needed.
 *
 * Concurrent callers join the same request, so a StrictMode effect replay or
 * two rapid clicks cannot ask Mission Control to launch a second process.
 * The destination always comes from the stored application definition.
 */
export function ensureApplicationStarted(applicationId: string): Promise<EnsureOpenResponse> {
  const existing = inFlight.get(applicationId);
  if (existing) return existing;
  const request = api.post<EnsureOpenResponse>(
    `/api/applications/${applicationId}/ensure-open`,
  );
  inFlight.set(applicationId, request);
  void request.then(
    () => {
      if (inFlight.get(applicationId) === request) inFlight.delete(applicationId);
    },
    () => {
      if (inFlight.get(applicationId) === request) inFlight.delete(applicationId);
    },
  );
  return request;
}

function writePlaceholder(popup: Window, label: string) {
  try {
    popup.opener = null;
    const document = popup.document;
    document.title = `Starting ${label}…`;
    if (document.body) {
      document.body.textContent = `Starting ${label}…`;
      document.body.style.fontFamily = "system-ui, sans-serif";
      document.body.style.padding = "28px";
      document.body.style.color = "#334155";
    }
  } catch {
    // A blocked or already-navigated popup must not prevent the launch.
  }
}

/**
 * Start a registered application if needed and open its verified loopback URL.
 *
 * The placeholder tab is opened synchronously so the browser keeps the click's
 * user gesture while the backend starts and verifies the engine. The URL is
 * never accepted from the browser.
 */
export async function ensureApplicationOpen(
  applicationId: string,
  label = applicationId,
): Promise<EnsureOpenResponse> {
  const popup = window.open("about:blank", "_blank");
  if (popup) writePlaceholder(popup, label);
  try {
    const result = await ensureApplicationStarted(applicationId);
    if (popup) {
      popup.opener = null;
      popup.location.replace(result.url);
    } else {
      window.location.assign(result.url);
    }
    return result;
  } catch (caught) {
    popup?.close();
    throw caught;
  }
}
