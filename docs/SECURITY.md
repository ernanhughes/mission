# Security model and verification

Mission Control is a local administrator tool: a person who can reach the local API is assumed to control the machine. The design still prevents a browser or request payload from turning that access into an unrestricted shell.

## Boundaries

1. **Network:** binds to `127.0.0.1` only. Startup refuses non-loopback hosts.
2. **Origins:** state-changing requests with an `Origin` header require an allowlisted local origin and `X-Mission-Control-Request: 1`. Local CLI clients without an Origin remain usable.
3. **Execution:** only stored, validated launch definitions. Launch requests accept `launch_id` and `confirm`; extra fields are rejected. No executable, cwd or shell command can be supplied at launch.
4. **Integration actions:** only registered adapter actions. The browser sends an action ID and schema-validated parameters, never a command. Adapter validation runs before an execution is queued. Approval-required actions need `confirm=true`.
5. **Process ownership:** only records created by Mission Control and still matching the recorded PID + creation time can be stopped. External listeners and guessed IDs are refused.
6. **Filesystem:** configured paths must be absolute, without `..` or device prefixes. Discovery roots must exist. Next SQLite reads use read-only mode. CoCoder review repositories must exactly match a registered repository path. CoCoder's own state is redirected into Mission Control's data directory.
7. **Environment:** child launches receive Windows essentials plus explicitly named variables. Unrelated secrets are not inherited. Integration DSNs are inherited by name only and never stored or returned.
8. **Secrets:** API keys are read from a named environment variable at request time. Only the variable name and a presence boolean are returned. Logs redact common key/token patterns. Secret-like integration configuration keys are removed from API responses.
9. **AI:** disabled by default; needs enablement + consent + configured endpoint/model. AI cannot execute tools. Calls are explicit.
10. **Data:** SQLite is local; no telemetry or outbound calls except configured health URLs and explicitly requested AI/briefing calls.

## Shell-script launch policy

`.cmd`, `.bat` and `.ps1` are rejected as launchable executables. This avoids implicit shell semantics and makes argument passing deterministic. On Windows, `PATH` commands that resolve to `.cmd` (for example the `code` shim) are also rejected for the editor; configure the native `Code.exe`.

## Origin guard behavior

- `GET`/`HEAD` requests are not blocked by the origin guard.
- `POST`/`PATCH`/`DELETE` with no `Origin` are treated as local CLI requests and allowed.
- With an `Origin`, it must be one of:
  - `http://127.0.0.1:5173`
  - `http://localhost:5173`
  - `http://127.0.0.1:<configured port>`
  - `http://localhost:<configured port>`
- The custom local header is additionally required for all browser-originated mutations.

## Headers

Default responses include:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- restrictive `Permissions-Policy`
- `Content-Security-Policy` with `frame-ancestors 'none'`
- `connect-src` limited to self and the local Vite origin

Swagger `/docs` uses a route-specific relaxed CSP to allow its CDN assets and bootstrap. The application pages do not.

## Redaction

`redact_text` covers:

- `Authorization: Bearer <token>`
- `sk-...` API keys
- `api_key=`, `password=`, `secret=`, `token=` assignments

Process logs are redirected to files and redacted when read. On normal process exit the log file is also rewritten with redaction. The launch header never contains environment values. Arguments could contain a secret if an administrator puts one there; the UI should not be used to store secrets in argument strings.

## MC09 integration actions

- Action IDs are resolved from the adapter's static registry. Unknown or disabled
  actions return 404/409.
- Parameters are checked against a JSON-schema subset before queueing: required
  fields, types, ranges and unknown-field rejection.
- CoCoder repository selection is checked against the registered application and
  project repository allowlist. Paths outside it return 422 before an execution
  record exists.
- CoCoder Git refs are restricted to a safe character set; shell metacharacters
  are rejected.
- Native executables only; `.cmd`, `.bat` and `.ps1` are rejected.
- Only one queued/running execution of the same action per application is allowed.
- Action output and errors are bounded before storage.
- CoCoder writes an explicit config that redirects its SQLite and artifacts under
  `data/integrations/cocoder/engine`; reviewing a repository does not create a
  repository-local `.cocoder` directory.
- Next reads PostgreSQL in a read-only transaction and uses SELECT statements
  only. No Next schema migration is executed by Mission Control.
- Work is read through `opportunities --json`; `work decide` and all Work write
  paths are not invoked.

Live acceptance verified: unregistered repository 422, injected parameter 422,
unconfirmed action 409, disabled Next action 409, and execution count unchanged
after all rejected attempts. See
[acceptance/mc09/security-check.json](acceptance/mc09/security-check.json).

## Tests

Backend security tests verify:

- browser origin rejection and header requirement;
- security headers;
- extra launch fields rejected (cannot inject executable/cwd);
- shell metacharacters and `.cmd` executables rejected;
- traversal and relative paths rejected;
- discovery traversal/relative roots rejected;
- AI API keys rejected from settings and absent from responses;
- external/guessed process IDs refused;
- log redaction;
- arbitrary stop via guessed ID -> 404/409;
- integration action schema rejects extra command fields;
- CoCoder review rejects unregistered repositories and unsafe refs before queueing;
- failed source refresh does not break other workspaces;
- CoCoder engine state is redirected outside the reviewed repository.

## Residual risks and limitations

- Any local process running as the same Windows user can read the SQLite database or logs. Mission Control is not a multi-user service.
- A deliberately configured malicious executable can do what that executable does. The registry is an administrative allowlist, not a sandbox.
- Health URLs are configured by an administrator and are not user-supplied per request.
- The API key lives in the environment of the Mission Control process; protect the environment and OS account.
- External applications may write their own secrets into logs before Mission Control reads them; on-read redaction covers common patterns but is not a guarantee about arbitrary secret formats.
- SQLite and `data/` are not encrypted at rest. CoCoder review artifacts can contain source excerpts and are stored there.
- The optional Next PostgreSQL credential lives in the process environment; read-only database grants are the defence if the process environment is compromised.
- CoCoder review executes the configured CoCoder executable. A malicious replacement executable would run with the user's privileges; the executable path is administrative configuration, not a sandbox.
- Windows process reattachment depends on a stable long-lived root PID. A launcher that exits immediately after spawning a grandchild is reported as lost rather than guessed. Do not force-stop processes outside Mission Control.
