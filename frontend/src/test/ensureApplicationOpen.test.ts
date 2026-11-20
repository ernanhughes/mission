import { describe, expect, it } from "vitest";
import { ensureApplicationStarted } from "../features/applications/ensureApplicationOpen";
import { json, mockFetch } from "./helpers";

describe("ensureApplicationStarted", () => {
  it("coalesces concurrent start requests for the same engine", async () => {
    const result = {
      url: "http://127.0.0.1:8000/",
      application_id: "engine-coalesce",
      state: "started",
      ownership: "managed",
      process_id: "proc-1",
      detail: "ready",
    };
    const calls = mockFetch(({ path, method }) => {
      if (path === "/api/applications/engine-coalesce/ensure-open" && method === "POST") {
        return json(result);
      }
      return json({}, 404);
    });

    const [first, second] = await Promise.all([
      ensureApplicationStarted("engine-coalesce"),
      ensureApplicationStarted("engine-coalesce"),
    ]);

    expect(first).toEqual(result);
    expect(second).toEqual(result);
    expect(
      calls.filter((call) => call.path === "/api/applications/engine-coalesce/ensure-open"),
    ).toHaveLength(1);
  });
});
