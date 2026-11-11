"""Print passages for human adjudication (EXPO-02 Stage C3)."""
import json
import sys

recs = [json.loads(line) for line in open("scripts/expo02/passages.jsonl", encoding="utf-8")]
only = sys.argv[1:] or None
for r in recs:
    if only and r["id"] not in only:
        continue
    print(f"===== {r['id']} [{r['selection']}] {r['source']} L{r['start_line']}-{r['end_line']} "
          f"rule={r['rule_flagged']}/{r['rule_subtype']} comp={r['compression']} intr={r['interruption']} "
          f"words={r['words']} sents={r['sentences']} label={r['provisional_label']}")
    print(r["text"][:1500])
    print()
