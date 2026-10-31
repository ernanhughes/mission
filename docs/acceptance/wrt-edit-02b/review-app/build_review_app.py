from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02b\review-app")
PACKET = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02b\review-packet")
DATA = Path(r"C:\Projects\mission\docs\acceptance\wrt-edit-02a\calibration-passages.json")
BLIND = PACKET / "calibration-blind-passages.csv"
TEMPLATE = ROOT / "review-app-template.html"
OUTPUT = ROOT / "WRT-EDIT-02B-review.html"
BATCH_COUNT = 5

passages = json.loads(DATA.read_text(encoding="utf-8"))["passages"]
blind = list(csv.DictReader(BLIND.open(encoding="utf-8", newline="")))
blind_by_id = {row["passage_id"]: row["text"] for row in blind}
assert len(passages) == 50
assert len(blind_by_id) == 50
for passage in passages:
    assert blind_by_id[passage["passage_id"]] == passage["text"], passage["passage_id"]

# Distribute the 50 passages into five balanced sets of ten without exposing
# the diagnostic labels in the reviewer page.
batches: list[list[dict]] = [[] for _ in range(BATCH_COUNT)]

def batch_cost(index: int, passage: dict) -> tuple:
    batch = batches[index]
    profile_count = sum(1 for item in batch if item["profile"] == passage["profile"])
    stratum_count = sum(
        1 for item in batch if item["diagnostic_stratum"] == passage["diagnostic_stratum"]
    )
    category_count = sum(1 for item in batch if item["category"] == passage["category"])
    return (len(batch), profile_count, stratum_count, category_count, index)

for passage in sorted(
    passages,
    key=lambda item: (
        item["profile"],
        item["diagnostic_stratum"],
        item["category"],
        item["passage_id"],
    ),
):
    index = min(range(BATCH_COUNT), key=lambda candidate: batch_cost(candidate, passage))
    batches[index].append(passage)

assert all(len(batch) == 10 for batch in batches), [len(batch) for batch in batches]

# Interleave each set so technical/fiction and categories are not clustered.
ordered_batches = []
for batch in batches:
    ordered = sorted(
        batch,
        key=lambda item: hashlib.sha256(f"WRT-EDIT-02B::{item['passage_id']}".encode()).hexdigest(),
    )
    ordered_batches.append(ordered)

app_passages = []
batch_assignment = []
for batch_number, batch in enumerate(ordered_batches, 1):
    for passage in batch:
        app_passages.append(
            {
                "id": passage["passage_id"],
                "text": passage["text"],
                "batch": batch_number,
            }
        )
        batch_assignment.append(
            {
                "passage_id": passage["passage_id"],
                "batch": batch_number,
            }
        )

# Restore canonical P01..P50 order for the full-50 view and CSV export.
app_passages.sort(key=lambda item: item["id"])

payload = json.dumps(app_passages, ensure_ascii=False).replace("</", "<\\/")
html = TEMPLATE.read_text(encoding="utf-8").replace("__PASSAGES_JSON__", payload)
OUTPUT.write_text(html, encoding="utf-8")

with (ROOT / "batch-assignment.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["passage_id", "batch"])
    writer.writeheader()
    writer.writerows(sorted(batch_assignment, key=lambda item: item["passage_id"]))

readme = """# WRT-EDIT-02B review app

Open `WRT-EDIT-02B-review.html` in a browser.

- The page starts with **Set 1 of 5**: 10 passages.
- Score each passage with the buttons, then click **Next**.
- At the end of the set you can download a CSV and stop, or continue to the
  next set.
- The CSV always has 50 rows in the original `P01`–`P50` order. Unscored rows
  are blank, so a 10-passage review produces a valid partial CSV.
- Answers are saved in this browser's local storage. Download the CSV before
  clearing browser data or switching machines.
- The page contains no book names, diagnostic categories, Writer scores or
  findings. It makes no network requests.
- The reviewer field is prefilled as **AI-assisted reviewer (prior diagnostic
  exposure)**. Change it if needed.

The page is a convenience wrapper around the frozen blind packet. The canonical
packet remains `calibration-blind-passages.csv` and
`calibration-review-template.csv` in `../review-packet/`.
"""
(ROOT / "README-review-app.md").write_text(readme, encoding="utf-8")

manifest = {
    "schema": "wrt-edit-02b.review-app.v1",
    "passage_count": len(app_passages),
    "batch_count": BATCH_COUNT,
    "passages_per_batch": 10,
    "diagnostic_key_included": False,
    "labels_included": False,
    "files": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "WRT-EDIT-02B-review.html",
            "batch-assignment.csv",
            "README-review-app.md",
        )
    },
}
(ROOT / "APP-MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print("passages", len(app_passages), "batches", [len(batch) for batch in ordered_batches])
for number, batch in enumerate(ordered_batches, 1):
    print(
        "batch",
        number,
        Counter(item["profile"] for item in batch),
        Counter(item["diagnostic_stratum"] for item in batch),
    )
print("html bytes", OUTPUT.stat().st_size)
