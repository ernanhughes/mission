import { ensureApplicationOpen } from "./ensureApplicationOpen";

export const WORKBENCH_APP_ID = "workbench";

/**
 * One-click Workbench open: start the registered application only when
 * needed, then navigate to its verified loopback URL.
 *
 * A popup opened after an awaited request is commonly blocked. The shared
 * helper opens the placeholder tab synchronously, then lets the backend
 * resolve the authoritative URL. The destination always comes from the
 * stored application definition.
 */
export async function ensureWorkbenchOpen(): Promise<string> {
  const result = await ensureApplicationOpen(WORKBENCH_APP_ID, "Workbench");
  return result.url;
}
