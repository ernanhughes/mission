# W8D-GIT-EVIDENCE — Five distinct relations, one new resolver kind

Commit relations, kept distinct (§13): created / mentioned / reachable /
merged / present-on-remote. History is never rewritten; no
commit-message conventions imposed. Association rows keep repository
identity + exact resolvable refs (the W6 bare-SHA lesson: resolver and
writer must agree on `uid:sha` form — regression-tested).

New in W8: `remote_ref` evidence kind (cited-but-unverified class,
resolves by citation like file/test_report/review; verdicts stay
reported). Pilot: `origin/main@https://…/ai.git contains 88b7c04`
human-attested → requirement satisfied_reported, mechanically and
correctly NOT verified (no independent execution of the check inside
Mission Control — the check ran in the pilot harness, recorded as
`reported_complete`, re-runnable by anyone).

Reachability vs proof, preserved from W6/W7: merged-into-main ≠
pushed; present-on-remote ≠ functionally correct; a later commit never
corroborates the original historical claim — only the stated revision
at the stated ref counts.
