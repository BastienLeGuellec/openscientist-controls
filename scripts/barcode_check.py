"""List every line of analysis code in our runs that touches cell names, barcodes or the obs index, so that one can
check by eye that no run used barcodes (which identify the sequencing library) to recover the original labels.

Usage: python3 -I scripts/barcode_check.py   (writes runs/audit/barcode_check.txt)
"""
import json
import re
from pathlib import Path

MA = Path(__file__).resolve().parents[1]
PAT = re.compile(r"obs_names|barcode|obs\.index|\.index\.str|cell_id|CellID", re.I)
RUNS = sorted(p.parent.parent.name for p in (MA / "runs").glob("*/artifacts/final_report.md")
              if not p.parent.parent.name.startswith("ma2_"))
out = []
for run in RUNS:
    hits = []
    for p in sorted((MA / "runs" / run / "artifacts/provenance").glob("iter*_transcript.json")):
        try:
            blocks = json.loads(p.read_text())
        except ValueError:
            continue
        for b in blocks if isinstance(blocks, list) else []:
            if b.get("type") == "tool_call" and "execute_code" in str(b.get("tool")):
                for line in str((b.get("arguments") or {}).get("code", "")).splitlines():
                    if PAT.search(line):
                        hits.append(f"    {p.name.split('_')[0]}: {line.strip()[:140]}")
    out.append(f"== {run}: {len(hits)} lines")
    out.extend(hits)
(MA / "runs/audit/barcode_check.txt").write_text("\n".join(out) + "\n")
print("\n".join(l for l in out if l.startswith("==")))
