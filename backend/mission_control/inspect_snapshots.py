"""Read-only Inspect consumer-snapshot loader (MC-INSPECT-01 Stage 3).

The snapshot at ``settings.inspect_dir`` is the ONLY interface between
Inspect and Mission Control: plain JSON files (manifest + datasets). This
module performs no Pi runs, no subprocess calls, no network calls and no
database writes -- it only reads files under the configured snapshot root.

Fail-safe behaviour (per ``docs/contract-mission.md`` in Inspect):
- missing/unreadable snapshot -> ``available: False`` empty state, never an
  exception at startup or request time;
- invalid refresh (bad structure, unsupported contract major version,
  checksum mismatch, unparseable JSON) -> keep serving the last valid
  snapshot and report ``stale_refresh: True``;
- only a fully validated snapshot replaces the cache.

There are no user-supplied filesystem paths anywhere in this feature: the
only files read are a fixed set of dataset names joined to the configured
root, and every resolved path is asserted to stay within that root. Request
``{id}`` path parameters are lookup keys into already-loaded in-memory data,
never converted to file paths (ids containing traversal sequences are
rejected before any lookup).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from mission_control.core.paths import is_within, normalize_absolute_path

logger = logging.getLogger(__name__)

EXPECTED_CONTRACT_MAJOR = "1"

MANIFEST_NAME = "manifest.json"

# Fixed dataset filenames -- the only files this module ever reads. There is
# deliberately no way for a request parameter to add or change an entry here.
DATASET_FILES = (
    "projects.json",
    "capabilities.json",
    "usage.json",
    "opportunities.json",
    "coverage.json",
    "compositions.json",
)

# Plural top-level keys holding the record lists in the merged consumer files.
DATASET_KEYS = {
    "projects.json": ("projects",),
    "capabilities.json": ("capabilities",),
    "usage.json": ("usages",),
    "opportunities.json": ("opportunities",),
    "coverage.json": ("coverages", "coverage"),
    "compositions.json": ("compositions",),
}

# Inspect ids that map to Mission application ids by identity. Everything else
# resolves via repository_path equality against the Application registry, and
# unknown ids pass through unmapped. Display names are never used for mapping.
IDENTITY_MAPPED_IDS = ("writer", "mission")


class _SnapshotUnavailable(Exception):
    """No snapshot can be served yet (missing dir/manifest)."""


class _SnapshotInvalid(Exception):
    """A refresh candidate failed validation and must not replace the cache."""


@dataclass
class SnapshotData:
    manifest: dict
    projects: list[dict] = field(default_factory=list)
    capabilities: list[dict] = field(default_factory=list)
    usages: list[dict] = field(default_factory=list)
    opportunities: list[dict] = field(default_factory=list)
    coverages: list[dict] = field(default_factory=list)
    compositions: list[dict] = field(default_factory=list)


def _read_json_locked(root: Path, name: str) -> tuple[bytes, object]:
    """Read one fixed dataset file, asserting it stays inside the root.

    ``name`` must be one of the module constants above -- callers never pass
    request-derived values here (asserted).
    """
    assert name in (MANIFEST_NAME, *DATASET_FILES), f"unexpected snapshot file: {name!r}"
    candidate = (root / name).resolve(strict=False)
    if not is_within(candidate, root):
        raise _SnapshotInvalid(f"snapshot file escapes root: {name}")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise _SnapshotInvalid(f"cannot read {name}: {exc}") from exc
    try:
        return raw, json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise _SnapshotInvalid(f"cannot parse {name}: {exc}") from exc


def _validate_manifest(document: object) -> dict:
    if not isinstance(document, dict):
        raise _SnapshotInvalid("manifest must be a JSON object")
    for key in ("contract_version", "generated_at", "inspect_version", "sources", "checksums"):
        if key not in document:
            raise _SnapshotInvalid(f"manifest is missing required key: {key}")
    version = document["contract_version"]
    if not isinstance(version, str) or not version:
        raise _SnapshotInvalid("manifest contract_version must be a non-empty string")
    major = version.split(".")[0]
    if major != EXPECTED_CONTRACT_MAJOR:
        raise _SnapshotInvalid(
            f"unsupported contract_version {version!r} "
            f"(expected major {EXPECTED_CONTRACT_MAJOR}); keeping last valid snapshot"
        )
    if not isinstance(document["sources"], list):
        raise _SnapshotInvalid("manifest sources must be a list")
    if not isinstance(document["checksums"], dict):
        raise _SnapshotInvalid("manifest checksums must be an object")
    return document


def _verify_checksums(root: Path, manifest: dict) -> None:
    checksums = manifest["checksums"]
    for name, expected in checksums.items():
        # Only verify files inside the snapshot root; anything else is rejected
        # rather than read.
        if not isinstance(name, str) or not name.endswith(".json"):
            raise _SnapshotInvalid(f"unexpected checksum entry: {name!r}")
        if "/" in name or "\\" in name or name.startswith("."):
            raise _SnapshotInvalid(f"checksum entry escapes snapshot root: {name!r}")
        assert name in DATASET_FILES or name == MANIFEST_NAME, (
            f"unexpected snapshot file: {name!r}"
        )
        candidate = (root / name).resolve(strict=False)
        if not is_within(candidate, root):
            raise _SnapshotInvalid(f"snapshot file escapes root: {name}")
        if not candidate.is_file():
            raise _SnapshotInvalid(f"checksummed file is missing: {name}")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if not isinstance(expected, str) or digest != expected.lower():
            raise _SnapshotInvalid(f"checksum mismatch for {name}")


def _record_list(document: object, filename: str) -> list[dict]:
    if not isinstance(document, dict):
        raise _SnapshotInvalid(f"{filename} must be a JSON object")
    for key in DATASET_KEYS[filename]:
        value = document.get(key)
        if value is None:
            continue
        if not isinstance(value, list):
            raise _SnapshotInvalid(f"{filename}.{key} must be a list")
        return [item for item in value if isinstance(item, dict)]
    return []


def _current_mtime(root: Path) -> float | None:
    """Newest mtime (ns) over manifest + datasets, or None if no manifest."""
    manifest_path = root / MANIFEST_NAME
    try:
        if not manifest_path.is_file():
            return None
    except OSError:
        return None
    newest = 0
    for name in (MANIFEST_NAME, *DATASET_FILES):
        try:
            stat = (root / name).stat()
        except OSError:
            continue
        newest = max(newest, stat.st_mtime_ns)
    return float(newest) if newest else None


def normalize_repository_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return os.path.normcase(os.path.normpath(value.strip()))
    except (ValueError, OSError):
        return None


def map_inspect_project(
    inspect_id: str,
    inspect_path: object,
    applications: list[object],
) -> tuple[str, bool]:
    """Resolve an Inspect project id to a Mission application id.

    Identity mapping applies to ``writer``/``mission``; otherwise equality on
    ``repository_path`` against the Application registry wins. Unknown ids pass
    through with ``mapped=False``. Display names are never consulted.
    """
    if inspect_id in IDENTITY_MAPPED_IDS:
        return inspect_id, True
    wanted = normalize_repository_path(inspect_path)
    if wanted:
        for app in applications:
            repo_path = getattr(app, "repository_path", None)
            candidate = normalize_repository_path(repo_path)
            if candidate and candidate == wanted:
                app_id = getattr(app, "id", None)
                if isinstance(app_id, str) and app_id:
                    return app_id, True
    return inspect_id, False


class InspectSnapshotStore:
    """In-memory cache of the last valid snapshot for one snapshot root."""

    def __init__(self, root: Path) -> None:
        normalized = normalize_absolute_path(str(root), field="inspect snapshot dir")
        self.root = Path(normalized)
        self._lock = threading.Lock()
        self._data: SnapshotData | None = None
        self._mtime: float | None = None
        self._stale_refresh = False

    def _load_candidate(self) -> tuple[SnapshotData, float | None]:
        _, manifest_doc = _read_json_locked(self.root, MANIFEST_NAME)
        manifest = _validate_manifest(manifest_doc)
        _verify_checksums(self.root, manifest)
        datasets: dict[str, list[dict]] = {}
        for name in DATASET_FILES:
            path = self.root / name
            if not path.is_file():
                # Files absent from the manifest checksums are optional.
                datasets[name] = []
                continue
            _, document = _read_json_locked(self.root, name)
            datasets[name] = _record_list(document, name)
        data = SnapshotData(
            manifest=manifest,
            projects=datasets["projects.json"],
            capabilities=datasets["capabilities.json"],
            usages=datasets["usage.json"],
            opportunities=datasets["opportunities.json"],
            coverages=datasets["coverage.json"],
            compositions=datasets["compositions.json"],
        )
        return data, _current_mtime(self.root)

    def refresh(self) -> SnapshotData | None:
        """Reload if files changed; fail safe, never raise for bad data."""
        with self._lock:
            try:
                current = _current_mtime(self.root)
            except Exception:
                logger.exception("Inspect snapshot mtime check failed")
                current = None
            if self._data is not None and current == self._mtime:
                return self._data
            if current is None:
                # No manifest: keep serving the last valid snapshot as stale;
                # with no cache there is simply nothing to serve.
                if self._data is not None:
                    self._stale_refresh = True
                return self._data
            try:
                data, mtime = self._load_candidate()
            except _SnapshotUnavailable as exc:
                logger.warning("Inspect snapshot unavailable: %s", exc)
                if self._data is not None:
                    self._stale_refresh = True
                return self._data
            except _SnapshotInvalid as exc:
                logger.warning("Inspect snapshot refresh rejected: %s", exc)
                if self._data is not None:
                    self._stale_refresh = True
                return self._data
            except Exception:
                logger.exception("Inspect snapshot refresh failed unexpectedly")
                if self._data is not None:
                    self._stale_refresh = True
                return self._data
            self._data = data
            self._mtime = mtime
            self._stale_refresh = False
            return self._data

    @property
    def stale_refresh(self) -> bool:
        with self._lock:
            # Ensure the flag reflects the current on-disk state.
            self.refresh()
            return self._stale_refresh

    def view(self) -> tuple[SnapshotData | None, bool]:
        data = self.refresh()
        with self._lock:
            return data, self._stale_refresh


_STORES: dict[str, InspectSnapshotStore] = {}
_STORES_LOCK = threading.Lock()


def get_store(root: Path | str) -> InspectSnapshotStore:
    """Return the shared store for a snapshot root (one per normalized path)."""
    normalized = normalize_absolute_path(str(root), field="inspect snapshot dir")
    with _STORES_LOCK:
        store = _STORES.get(normalized)
        if store is None:
            store = InspectSnapshotStore(normalized)
            _STORES[normalized] = store
        return store


def clear_stores_for_tests() -> None:
    """Drop cached stores. Test-only helper so tmp snapshot dirs stay isolated."""
    with _STORES_LOCK:
        _STORES.clear()
