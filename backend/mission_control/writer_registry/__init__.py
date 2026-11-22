"""Writer registry integration plumbing (read-only)."""

from mission_control.writer_registry.adapter import (
    WriterBookDefinition,
    WriterRegistrySnapshot,
    load_writer_registry,
    resolve_registry_path,
)
from mission_control.writer_registry.sync import (
    book_source_diagnostic,
    sync_writer_books,
)

__all__ = [
    "WriterBookDefinition",
    "WriterRegistrySnapshot",
    "book_source_diagnostic",
    "load_writer_registry",
    "resolve_registry_path",
    "sync_writer_books",
]
