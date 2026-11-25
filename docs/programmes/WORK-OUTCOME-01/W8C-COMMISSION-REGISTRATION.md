# W8C-COMMISSION-REGISTRATION — Intent before execution

`POST /api/work-envelopes` registers prospective work. It validates
(episode exists; objective belongs to episode; every requirement id
resolves to the same episode; every finding id resolves; authorization
is an approved proposal or a named human + note) and returns the
envelope id + version + digest + requirement versions. Unknown refs are
rejected — nothing is invented. Identical digests return `duplicate`;
material changes create version+1 and supersede (history kept).

Pre-execution binding is real: in the pilot, objective + 3 requirements
+ authorization existed BEFORE the git checks ran (22:16 registration
→ execution → 22:19 evaluation). An AI implementation decision cannot
silently change the authorized objective — re-registration is a new
version with a new digest, and evaluation joins requirement versions
at assessment time.

Amendments flow: requirement amend → new WoRequirement version
(supersedes old) → envelope re-registration binds the new version.
Stale envelopes (superseded) stay readable; the active row is
unambiguous.
