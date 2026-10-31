import { api } from "../../api/client";
import type { Application } from "../../types/api";

export function applicationBrowserUrl(app: Application): string | null {
  return (
    app.launch_definitions.find((definition) => definition.enabled && definition.browser_url)
      ?.browser_url ?? null
  );
}

/**
 * Open the configured browser URL without losing the click's user gesture.
 *
 * A popup opened after an awaited request is commonly blocked. Opening the
 * placeholder tab synchronously keeps the browser's allowance, then the API
 * resolves the authoritative URL and records the open in Mission Control.
 */
export async function openApplicationUrl(appId: string): Promise<string> {
  const popup = window.open("about:blank", "_blank");
  try {
    const result = await api.post<{ url: string; opened_externally?: boolean }>(
      `/api/applications/${appId}/open-url`,
    );
    if (result.opened_externally) {
      popup?.close();
    } else if (popup) {
      popup.opener = null;
      popup.location.replace(result.url);
    } else {
      window.location.assign(result.url);
    }
    return result.url;
  } catch (caught) {
    popup?.close();
    throw caught;
  }
}
