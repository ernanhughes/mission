from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from writer_core.projects.paths import load_registry
from writer_runtime.projects.manuscript_scope import ProjectManuscriptResolver

OUT = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02a")
label = sys.argv[1]
assert label in {"before", "after"}

registry = load_registry()
resolver = ProjectManuscriptResolver(registry=registry)
projects = []
overall = hashlib.sha256()
total_files = 0
total_errors = 0

for project in sorted(registry.list_active(), key=lambda p: p.key):
    chapter_paths = []
    error = ""
    try:
        chapter_paths = resolver.list_chapter_paths(project.key)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    editing = [
        path
        for path in chapter_paths
        if path.is_file()
        and path.suffix.lower() in {".md", ".markdown"}
        and not path.stem.startswith("_")
    ]
    project_digest = hashlib.sha256()
    files = []
    errors = []
    for path in sorted(editing):
        try:
            payload = path.read_bytes()
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue
        try:
            relative = path.relative_to(project.content_dir).as_posix()
        except ValueError:
            relative = path.as_posix()
        project_digest.update(relative.encode())
        project_digest.update(b"\0")
        project_digest.update(payload)
        project_digest.update(b"\0")
        overall.update(project.key.encode())
        overall.update(b"\0")
        overall.update(relative.encode())
        overall.update(b"\0")
        overall.update(payload)
        overall.update(b"\0")
        files.append({"relative_path": relative, "path": str(path), "bytes": len(payload)})
    total_files += len(files)
    total_errors += len(errors)
    projects.append(
        {
            "project_id": project.key,
            "content_dir": str(project.content_dir),
            "chapter_count": len(editing),
            "sha256": project_digest.hexdigest() if editing else None,
            "files": files,
            "errors": errors[:20],
            "resolution_error": error,
        }
    )

result = {
    "schema": "wrt-edit-02a.manuscript-hashes.v2",
    "registry_sha256": hashlib.sha256(
        Path(r"C:\Projects\writer\config\web\projects.yaml").read_bytes()
    ).hexdigest(),
    "project_count": len(projects),
    "chapter_files": total_files,
    "errors": total_errors,
    "aggregate_sha256": overall.hexdigest(),
    "projects": projects,
}
(OUT / f"manuscript-hashes-{label}.json").write_text(
    json.dumps(result, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {
            "label": label,
            "registry_sha256": result["registry_sha256"],
            "project_count": result["project_count"],
            "chapter_files": result["chapter_files"],
            "errors": result["errors"],
            "aggregate_sha256": result["aggregate_sha256"],
        },
        indent=2,
    )
)
