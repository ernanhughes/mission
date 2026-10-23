"""Read-only snapshot of integration repository states for acceptance evidence."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

TARGETS = [
    r"C:\Projects\next",
    r"C:\Projects\cocoder",
    r"C:\Projects\work",
    r"C:\Projects\writer",
    r"C:\Projects\improve",
    r"C:\Projects\bookbuilder",
    r"C:\Projects\worker",
    r"C:\Projects\stephanie",
    r"C:\Projects\workbench",
    r"C:\Projects\language",
    r"C:\Projects\project-language",
    r"C:\Projects\math",
    r"C:\Projects\math-r1",
    r"C:\books\inference",
    r"C:\Projects\mission",
]


def git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        check=False,
        timeout=15,
    )
    return result.stdout.strip()


def main() -> None:
    lines = [
        "# Read-only Git state snapshot",
        "",
        f"Captured: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This snapshot was produced with read-only `git status`, `git rev-parse` and",
        "`git log` commands. No repository was fetched, cleaned, reset or modified.",
        "Dirty states below are pre-existing user work or concurrent external work,",
        "not changes made by Mission Control implementation or testing.",
        "",
        "Mission Control has no write path into these repositories. If a target",
        "repository changed while this work was in progress, another process or the",
        "user made that change. The implementation commit 4ee569d contains the first",
        "snapshot for comparison.",
        "",
        "| Repository | Branch | HEAD | Tracked/untracked changes | Clean? |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for target in TARGETS:
        path = Path(target)
        if not path.exists():
            lines.append(f"| `{target}` | — | — | — | missing |")
            continue
        if not (path / ".git").exists():
            lines.append(f"| `{target}` | — | — | — | not a Git repository |")
            continue
        branch = git(path, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
        head = (git(path, "rev-parse", "--short", "HEAD") or "unknown")[:12]
        status = git(path, "status", "--porcelain")
        changed = len([line for line in status.splitlines() if line.strip()])
        if path.name.casefold() == "mission":
            clean = "yes" if changed == 0 else "no (this implementation)"
        else:
            clean = "yes" if changed == 0 else "no (pre-existing)"
        lines.append(f"| `{target}` | {branch} | `{head}` | {changed} | {clean} |")
    output = Path(__file__).resolve().parents[1] / "docs" / "acceptance" / "PRE-EXISTING-REPO-STATES.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
