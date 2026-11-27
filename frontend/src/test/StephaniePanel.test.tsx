import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { contextForMissionProject, makeStephanieContext, StephaniePanelProvider, useStephaniePanel } from "../features/stephanie/StephaniePanel";
import type { ProjectDetail, ProjectGitLink } from "../types/api";

function Harness() {
  const panel = useStephaniePanel();
  return <>
    <button onClick={() => panel.openStephanie(makeStephanieContext("writer", "a".repeat(40), "commit-details"))}>Open Writer commit</button>
    <button onClick={() => panel.openStephanie(makeStephanieContext("mission", "b".repeat(40), "project-detail"))}>Switch context</button>
    <button onClick={panel.closeStephanie}>Close panel</button>
  </>;
}

describe("Mission Control Stephanie panel", () => {
  it("attaches a project's indexed primary HEAD and never guesses latest", () => {
    const project = { id:"writer", repositories:[{id:"repo-main",role:"primary",commit_hash:null}] } as unknown as ProjectDetail;
    const links = [{repository_id:"repo-main",role:"primary",head_sha:"c".repeat(40)}] as ProjectGitLink[];
    expect(contextForMissionProject(project, links)).toMatchObject({subject:"writer",revision:"c".repeat(40),view:"project-detail"});
    expect(contextForMissionProject(project, [])).toMatchObject({subject:"writer",revision:null});
  });

  it("posts the bounded versioned context to the existing SIS iframe", () => {
    render(<StephaniePanelProvider><Harness /></StephaniePanelProvider>);
    fireEvent.click(screen.getByRole("button", {name:"Open Writer commit"}));
    const frame = screen.getByTitle("Stephanie prompt generator") as HTMLIFrameElement;
    expect(frame.getAttribute("src")).toBe("http://127.0.0.1:8766/stephanie");
    expect(frame.getAttribute("allow")).toBe("clipboard-write");
    const postMessage = vi.spyOn(frame.contentWindow!, "postMessage");
    fireEvent.load(frame);
    expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({
      schema_version:"stephanie.context.v1", event_type:"stephanie.open", application:"mission",
      context_type:"repository", subject:"writer", revision:"a".repeat(40), view:"commit-details",
    }), "http://127.0.0.1:8766");
  });

  it("replaces the active context and discards it when the panel closes", () => {
    render(<StephaniePanelProvider><Harness /></StephaniePanelProvider>);
    fireEvent.click(screen.getByRole("button", {name:"Open Writer commit"}));
    const frame = screen.getByTitle("Stephanie prompt generator") as HTMLIFrameElement;
    const postMessage = vi.spyOn(frame.contentWindow!, "postMessage");
    fireEvent.load(frame);
    fireEvent.click(screen.getByRole("button", {name:"Switch context"}));
    expect(postMessage).toHaveBeenLastCalledWith(expect.objectContaining({subject:"mission",revision:"b".repeat(40)}), "http://127.0.0.1:8766");
    expect(screen.getByLabelText("Stephanie contextual assistant")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name:"Close panel"}));
    expect(screen.queryByLabelText("Stephanie contextual assistant")).not.toBeInTheDocument();
  });

  it("reposts context after the iframe completes a redirect or reload", () => {
    render(<StephaniePanelProvider><Harness /></StephaniePanelProvider>);
    fireEvent.click(screen.getByRole("button", {name:"Open Writer commit"}));
    const frame = screen.getByTitle("Stephanie prompt generator") as HTMLIFrameElement;
    const postMessage = vi.spyOn(frame.contentWindow!, "postMessage");
    fireEvent.load(frame);
    postMessage.mockClear();
    fireEvent.load(frame);
    expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({subject:"writer",revision:"a".repeat(40)}), "http://127.0.0.1:8766");
  });
});
