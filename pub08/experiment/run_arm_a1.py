"""PUB-08 Arm A replicate 1 — single paid whole-chapter dispatch (GO per design §5).

One shot, no retry, no repair. Prior PUB-08 actuals $0.00 + projection
$0.015 worst-case vs $1.00 cap (manual aggregate check inline: the
aggregate-wrapper CLI wiring is PUB-09 work).
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

MISSION = Path(r"C:\Projects\mission")
EXP = MISSION / "pub08" / "experiment"
OUT = EXP / "arm_a_r1"

# Single source: prompt builder + DTO live in the batch-2 gate module.
spec = importlib.util.spec_from_file_location(
    "arm_a_gate",
    r"C:\Projects\writer\tests\core\test_pub08_arm_a_gate.py")
arm_a_gate = importlib.util.module_from_spec(spec)
sys.modules["arm_a_gate"] = arm_a_gate
spec.loader.exec_module(arm_a_gate)

# 1. Freeze check: rebuilt prompt must equal the frozen bytes exactly.
freeze = json.loads((EXP / "freeze.json").read_text(encoding="utf-8"))
frozen_prompt_sha = freeze["arm_a"]["prompt_artifact"]["sha256"]
o_text = Path(r"C:\books\jev\content\books\jev\01-chapter.md").read_text(
    encoding="utf-8")
# Construction note (verified): the frozen prompt embeds O WITHOUT its
# single trailing newline (both rstrip and splitlines-join reproduce
# the frozen SHA exactly). The full O bytes (with trailing newline)
# remain the frozen source of truth in freeze.json.
prompt = arm_a_gate.build_arm_a_prompt(o_text.rstrip("\n"))
prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
assert prompt_sha == frozen_prompt_sha, (prompt_sha, frozen_prompt_sha)
frozen_file = (EXP / "arm_a_prompt.txt").read_bytes().decode("utf-8")
assert prompt == frozen_file, "prompt drift vs frozen file"
print("prompt SHA matches freeze:", prompt_sha[:12])

# 2. Manual aggregate spend check (wrapper CLI wiring is PUB-09).
prior, projection, cap = 0.0, 0.015, 1.00
assert prior + projection <= cap, "aggregate cap would be exceeded"
print(f"aggregate check: prior ${prior:.4f} + proj ${projection:.4f} <= cap ${cap:.2f} OK")

# 3. Live seam (identical shape to the transform CLI live path).
sys.path.insert(0, r"C:\Projects\writer\packages\writer-runtime")
sys.path.insert(0, r"C:\Projects\writer\packages\writer-core")
from writer_runtime import build_runtime
from writer_runtime.domains.models.typed_task import run_typed_task
from writer_core.analysis import publication_automation as auto

runtime = build_runtime()
models = runtime.require("models")


def _dispatch(*, task, prompt, dto, metadata=None,
              context_for_provenance=None):
    return run_typed_task(
        models, task=task, prompt=prompt, dto=dto, domain="publication",
        operation_id="pub08-arm-a-ch1", stage_id="pub08-a1",
        metadata=dict(metadata or {}),
        context_for_provenance=context_for_provenance)


payload = {
    "task_kind": "publication_arm_a",
    "task": arm_a_gate.ARM_A_TASK,
    "model_override": arm_a_gate.ARM_A_MODEL_OVERRIDE,
    "package_id": "pub08:arm-a:ch1",
    "chapter_sha256": hashlib.sha256(o_text.encode("utf-8")).hexdigest(),
    "prompt": prompt,
    "attempt": 1,
}
record = auto.dispatch_task(
    _dispatch, payload, arm_a_gate.WholeChapterCandidateResponse,
    role="editorial")

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "dispatch-record.json").write_text(
    json.dumps(record, indent=1, default=str), encoding="utf-8")

prov = record.get("provenance", {}) or {}
usage = prov.get("usage", {}) or {}
print("status:", record.get("status"), "| succeeded:", record.get("succeeded"))
print("model:", prov.get("model"), "| route: default_deepseek_go")
print("usage:", json.dumps(usage), "| cost_usd:", prov.get("cost_usd"))

if record.get("succeeded") and record.get("typed"):
    lines = record["typed"]["chapter_lines"]
    (OUT / "candidate.md").write_bytes(
        ("\n".join(lines) + "\n").encode("utf-8"))
    print("candidate lines:", len(lines),
          "| sha:", hashlib.sha256(
              ("\n".join(lines) + "\n").encode()).hexdigest()[:12])
else:
    print("FAILURE RECORDED (no retry):", record.get("error"),
          record.get("error_kind"))
