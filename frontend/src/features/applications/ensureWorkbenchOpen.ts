import { api } from "../../api/client";

export type EnsureOpenResult = {
  url: string;
  application_id: string;
  state: string;
  ownership: string;
  process_id: string | null;
  detail: string | null;
};

export const WORKBENCH_APP_ID = "workbench";

/**
 * One-click Workbench open: start the registered application only when
 * needed, then navigate to its verified loopback URL.
 *
 * A popup opened after an awaited request is commonly blocked. Opening the
 * placeholder tab synchronously keeps the browser's allowance, then the
 * backend resolves the authoritative URL and this navigates that tab to it.
 * The destination always comes from the stored application definition.
 */
export async function ensureWorkbenchOpen(): Promise<string> {
  const popup = window.open("about:blank", "_blank");
  try {
    const result = await api.post<EnsureOpenResult>(
      `/api/applications/${WORKBENCH_APP_ID}/ensure-open`,
    );
    if (popup) {
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
