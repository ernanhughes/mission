# MC-WRITER-01 — Writer Editing integration

## Architectural rule

```text
Writer owns book intelligence and editing evidence.
Mission Control orchestrates Writer and exposes decisions.
Books remain the source artifacts.
```

Mission Control does not parse manuscripts, calculate readability or duplicate
Writer's findings. It consumes the versioned Writer CLI contract, displays
Writer's evidence and preserves source status.

## Writer boundary

Writer exposes `runtime.editing` and the CLI:

```text
writer editing summary --json
writer editing audit --all --json
writer editing audit PROJECT [--chapter SELECTOR] --json
writer editing reports --json
writer editing show REPORT_ID --json
writer editing status REPORT_ID --json
writer editing compare LEFT RIGHT --json
```

The report is `writer-editing-report-v1` (`1.0.0`) and contains independent
readability subdimensions, findings, locators, source fingerprints, errors,
partial state and a canonical result fingerprint. Writer stores reports under
its git-ignored `.writer/editing` artifact directory.

## Mission Control adapter

`backend/mission_control/adapters/writer.py`:

- uses the configured native Writer executable and structured arguments;
- never imports Writer's parser/scoring code;
- reads `writer editing summary --json`;
- validates `writer.editing.cli.v1` and `writer-editing-summary-v1`;
- stores one `writer_editing_book` resource per registered project;
- preserves partial results, errors, `NOT_RUN`, `STALE` and `BLOCKED` rather than
  converting them to zero or a pass;
- records Writer's `store_path`, report IDs and limitations as evidence.

The registered action `audit_registered_books` runs Writer's read-only audit
through Mission Control's durable `integration_executions` lifecycle. It requires
explicit confirmation and writes only Writer-owned report artifacts.

Configuration is discovered from the existing Writer application entry:

```yaml
integration:
  adapter: writer
  enabled: true
  config:
    executable: C:\Projects\writer\venv\Scripts\writer.exe
    working_directory: C:\Projects\writer
    arguments: [editing, summary, --json]
    timeout_seconds: 60
    env_names: [WRITER_PROJECTS_CONFIG]
```

`WRITER_PROJECTS_CONFIG` is optional and exists for a separate acceptance
registry. The normal registry remains `C:\Projects\writer\config\web\projects.yaml`.

## Mission Control read model

`backend/mission_control/writer/service.py` reads current Writer resources and
builds:

- book-level totals;
- a bounded review queue ordered by Writer status and risk;
- book rows with Metadata / MRI / Strengthen / Editing / Readability / Highest
  risk / Last checked;
- independent subdimension scores;
- chapter inventory with all six scores;
- raw metrics, findings, source locators and stale/current state;
- links back to Writer report IDs and paths.

Metadata, MRI and Strengthen are shown as `NOT_TRACKED` by Editing v1. The wider
pipeline is displayed, but Editing does not infer earlier-stage status or claim
that every book must run every stage before a read-only audit.

## UI

Route: `/writer` (**Writer** in the Engines navigation and command palette).

The page shows:

- cross-book review queue;
- book table with the pipeline columns and explicit states;
- selected-book readability summary;
- chapter table with independent scores (no single colour or composite);
- chapter drill-down with raw metrics, scoring weights, findings and line
  locators;
- stale/current state and Writer limitations;
- **Refresh Writer data** and **Run Writer audits** actions.

`NOT_RUN` is labelled as no evidence, not a pass. `STALE` includes the Writer
staleness detail.

## Failure and freshness rules

- Missing Writer executable or malformed CLI output → unavailable with a
  diagnostic; no rows are invented.
- Missing report → `NOT_RUN`.
- Changed source fingerprint → `STALE`.
- Selected-chapter-only report → `PARTIAL` at book level.
- Chapter/analysis failure → `PARTIAL` with retained errors.
- Invalid stored report → `ERROR`.
- Missing content path → `BLOCKED`.
- Non-Markdown project → `NO_MANUSCRIPT`.
- No automatic correction, manuscript editing, model call, publishing or
  acceptance is performed.

## Operational commands

```powershell
# Writer
cd C:\Projects\writer
venv\Scripts\writer.exe editing summary --json
venv\Scripts\writer.exe editing audit language --json
venv\Scripts\writer.exe editing audit --all --json

# Mission Control
cd C:\Projects\mission
.\scripts\start.ps1
# open http://127.0.0.1:8790/writer
```

## Next Editing milestone

`WRT-EDIT-02` should calibrate readability thresholds across accessible books,
add a second independent dimension (suggested: clarity or repetition), and
introduce asynchronous audit progress without changing the report contract.
`plan` and `apply` remain separately authorised future work.
