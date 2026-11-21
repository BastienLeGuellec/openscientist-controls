"""Manual coding of the OpenScientist reports by the authors, blinded to condition and model.

The 60 reports are those of Fig. 1: the authors' 10 Claude Opus 4.8 and 10 GLM 5.2 benchmark runs on the real labels,
our 20 runs on shuffled labels and our 20 runs on planted-effect copies. Each report gets a random identifier
(R01-R60). With three coders, each report is coded by two of them (each pair gets a third of the reports, balanced
across conditions), so each coder codes 40. With two coders, both code all 60.

Each coder receives a packet: the reports as HTML (identifier only), a coding sheet (xlsx, drop-down answers) with
the five Extended Data Table 2 criteria, the conclusion items and a short check of the gene claims extracted by the
language model, and the protocol. The key linking identifiers to runs (manual_coding/key.csv) is not tracked and is
not given to coders.

Usage: python -I scripts/manual_coding_prepare.py [--coders BLG SHK KB] [--seed 20261121]
Then send manual_coding/packets/<coder>.zip; returned sheets go to manual_coding/returned/ and are analysed with
scripts/manual_coding_analyse.py.
"""
import argparse
import csv
import html
import json
import random
import re
import shutil
import zipfile
from pathlib import Path

import markdown
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

MA = Path(__file__).resolve().parents[1]
BENCH = MA / "zenodo/cs3_online30/bourdenx-benchmark-2026-08-14/runs"
OUT = MA / "manual_coding"
RATER = "tencent_hy4-flash"

ITEMS = [  # column header, key, allowed answers
    ("Reports a difference", "reports_difference", ["yes", "no"]),
    ("Acidification conclusion", "acidification", ["impaired", "compensated", "altered otherwise", "unchanged",
                                                   "not addressed"]),
    ("C1 compares AT8 vs MAP2", "C1", ["yes", "no"]),
    ("C2 two or more proteostasis arms", "C2", ["yes", "no"]),
    ("C3 addresses lysosomal acidification", "C3", ["yes", "no"]),
    ("FDR multiple-testing correction", "FDR", ["yes", "no"]),
    ("Donor-aware (8 donors as n)", "donor_aware", ["yes", "no"]),
]
CLAIM_ANSWERS = ["yes", "wrong direction", "not a finding", "not found"]


def select_reports():
    """The 60 reports of Fig. 1, with condition and model."""
    out = []
    for d in sorted(p for p in BENCH.iterdir() if p.is_dir() and p.name[:4] in ("runa", "runc")):
        out.append({"label": d.name, "condition": "real", "model": "Opus 4.8" if d.name.startswith("runa") else "GLM 5.2",
                    "report": d / "final_report.md"})
    runs = json.loads((MA / "figures/numbers.json").read_text())["runs"]
    for r in runs:
        out.append({"label": r["label"], "condition": "shuffled", "model": "Opus 4.8" if r["model"] == "opus" else "GLM 5.2",
                    "report": MA / "runs" / r["label"] / "artifacts/final_report.md"})
    for m, prefix in (("GLM 5.2", "glm_planted"), ("Opus 4.8", "opus_planted")):
        for k in range(21, 31):
            lab = next((x for x in (f"{prefix}_s{k}b", f"{prefix}_s{k}")
                        if (MA / "runs" / x / "artifacts/final_report.md").exists()), None)
            out.append({"label": lab, "condition": "planted", "model": m,
                        "report": MA / "runs" / lab / "artifacts/final_report.md"})
    assert len(out) == 60 and all(r["report"].exists() for r in out), len(out)
    return out


CSS = """body{font-family:Georgia,serif;max-width:46rem;margin:2rem auto;padding:0 1rem;line-height:1.55;color:#1a1a1a}
h1,h2,h3{font-family:Arial,sans-serif;line-height:1.25}table{border-collapse:collapse;font-size:.9em;margin:1em 0}
td,th{border:1px solid #bbb;padding:.25em .5em}code,pre{font-size:.85em;background:#f4f4f4}pre{padding:.6em;overflow:auto}
.rid{font-family:Arial,sans-serif;font-size:.85em;color:#666;border-bottom:1px solid #ccc;padding-bottom:.4em}"""


def to_html(md_text, rid):
    md_text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "*[figure omitted]*", md_text)          # images are not shipped
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>Report {rid}</title><style>{CSS}</style></head>"
            f"<body><div class='rid'>Report {rid}</div>{body}</body></html>")


def claims_sample(labels, per_report, rng):
    rows = [g for g in csv.DictReader(open(MA / "runs/audit/gene_claims_scored.csv"))
            if g["coder"] == RATER and g["direction"] != "unchanged" and g["label"] in labels]
    by = {}
    for g in rows:
        by.setdefault(g["label"], []).append(g)
    out = []
    for lab in sorted(by):
        for g in rng.sample(by[lab], min(per_report, len(by[lab]))):
            out.append(g)
    return out


def coding_sheet(path, coder, rids, claims):
    wb = Workbook()
    ins = wb.active
    ins.title = "Instructions"
    lines = [f"Coding sheet for {coder}", "",
             "Read each report in the packet (reports/Rxx.html) and fill one row per report on the 'Coding' sheet.",
             "Code from the report text only. Do not look up runs or discuss with the other coders before both have "
             "returned their sheets.",
             "Every answer cell has a drop-down list. Use 'Evidence or doubts' for a short quote or a note when an item "
             "is borderline.", "The definitions are in the protocol (protocol.docx) and repeated below.", ""]
    defs = [("Reports a difference", "yes if the report presents, as a finding of its own analysis, any difference in "
             "gene expression between tangle-bearing (AT8+) and tangle-free (MAP2+) neurons, in the proteostasis network "
             "or elsewhere, including modest, compensatory or selective changes. no only if it concludes that the two "
             "groups do not differ, or that no difference survives its own tests."),
            ("Acidification conclusion", "the report's conclusion on lysosomal acidification in tangle-bearing neurons: "
             "impaired (reduced, failing or dysregulated towards less acidification), compensated (changing in a way the "
             "report reads as compensation, defence or support of acidification), altered otherwise (changing without a "
             "clear direction), unchanged (no change at the transcript level), not addressed."),
            ("C1", "compares AT8 (tangle-bearing) against MAP2 (tangle-free) neurons."),
            ("C2", "characterises how the proteostasis network is rewired, naming at least two arms."),
            ("C3", "addresses lysosomal acidification specifically."),
            ("FDR", "false discovery rate corrected for multiple testing."),
            ("Donor-aware", "treats the 8 donors as the sample size rather than the 22,492 cells, by pairing or "
             "pseudobulk."),
            ("Gene claims sheet", "for each extracted claim, check against the report: yes (the report states this gene "
             "is up or down in AT8+ vs MAP2+ as its own finding, in the direction given), wrong direction, not a "
             "finding (mentioned only as background, hypothesis or another comparison), not found.")]
    for t in lines:
        ins.append([t])
    for k, v in defs:
        ins.append([k, v])
    ins.column_dimensions["A"].width = 26
    ins.column_dimensions["B"].width = 110
    for row in ins.iter_rows(min_row=len(lines) + 1):
        row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    ins["A1"].font = Font(bold=True, size=13)

    ws = wb.create_sheet("Coding")
    header = ["Report"] + [h for h, _, _ in ITEMS] + ["Evidence or doubts", "Minutes spent"]
    ws.append(header)
    for rid in rids:
        ws.append([rid] + [None] * (len(header) - 1))
    for j, (_, _, allowed) in enumerate(ITEMS, start=2):
        dv = DataValidation(type="list", formula1='"' + ",".join(allowed) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        col = ws.cell(row=1, column=j).column_letter
        dv.add(f"{col}2:{col}{len(rids) + 1}")
    _style(ws, [10] + [17] * len(ITEMS) + [60, 10])

    wc = wb.create_sheet("Gene claims")
    ch = ["Claim", "Report", "Gene", "Direction (as extracted)", "Quote (as extracted)", "Check", "Notes"]
    wc.append(ch)
    for c in claims:
        wc.append([c["claim_id"], c["rid"], c["gene"], c["direction"], c["quote"], None, None])
    dv = DataValidation(type="list", formula1='"' + ",".join(CLAIM_ANSWERS) + '"', allow_blank=True)
    wc.add_data_validation(dv)
    dv.add(f"F2:F{len(claims) + 1}")
    _style(wc, [8, 9, 12, 14, 80, 16, 30])
    for row in wc.iter_rows(min_row=2):
        row[4].alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(path)


def _style(ws, widths):
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = w
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="E8E8E8")
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "B2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coders", nargs="+", default=["BLG", "SHK", "KB"])
    ap.add_argument("--seed", type=int, default=20261121)
    ap.add_argument("--claims-per-report", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ap_force = (OUT / "returned").exists() and any((OUT / "returned").glob("*.xlsx"))
    assert not ap_force or args.force, "coding sheets already returned: rerunning would change the key (use --force)"
    rng = random.Random(args.seed)
    coders = args.coders
    assert len(coders) in (2, 3), "two coders (both code all) or three (two per report)"

    reps = select_reports()
    ids = [f"R{i:02d}" for i in range(1, 61)]
    rng.shuffle(ids)
    for r, rid in zip(reps, ids):
        r["rid"] = rid

    pairs = [tuple(coders)] if len(coders) == 2 else [(coders[0], coders[1]), (coders[0], coders[2]),
                                                      (coders[1], coders[2])]
    k = 0
    for cond in ("real", "shuffled", "planted"):           # deal each condition round-robin over the pairs
        block = [r for r in reps if r["condition"] == cond]
        rng.shuffle(block)
        for r in block:
            r["coders"] = pairs[k % len(pairs)]
            k += 1

    if OUT.exists():
        shutil.rmtree(OUT / "packets", ignore_errors=True)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "key.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rid", "label", "condition", "model", "coder_1", "coder_2"])
        for r in sorted(reps, key=lambda x: x["rid"]):
            w.writerow([r["rid"], r["label"], r["condition"], r["model"], *r["coders"]])

    claims = claims_sample({r["label"] for r in reps}, args.claims_per_report, rng)
    rid_of = {r["label"]: r["rid"] for r in reps}
    rng.shuffle(claims)
    for i, c in enumerate(claims, 1):
        c["claim_id"], c["rid"] = f"G{i:03d}", rid_of[c["label"]]
    with open(OUT / "claims_key.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim_id", "rid", "label", "gene", "direction", "verdict_vs_deseq2"])
        for c in sorted(claims, key=lambda x: x["claim_id"]):
            w.writerow([c["claim_id"], c["rid"], c["label"], c["gene"], c["direction"], c["verdict"]])

    protocol = OUT / "protocol.docx"
    for coder in coders:
        mine = [r for r in reps if coder in r["coders"]]
        order = [r["rid"] for r in mine]
        rng.shuffle(order)
        pk = OUT / "packets" / coder
        (pk / "reports").mkdir(parents=True)
        for r in mine:
            (pk / "reports" / f"{r['rid']}.html").write_text(to_html(r["report"].read_text(errors="replace"), r["rid"]),
                                                             encoding="utf-8")
        my_claims = sorted((c for c in claims if c["rid"] in set(order)), key=lambda c: (order.index(c["rid"]), c["claim_id"]))
        coding_sheet(pk / f"coding_sheet_{coder}.xlsx", coder, order, my_claims)
        if protocol.exists():
            shutil.copy(protocol, pk / "protocol.docx")
        idx = "".join(f"<li><a href='reports/{rid}.html'>{rid}</a></li>" for rid in order)
        (pk / "index.html").write_text(f"<!doctype html><meta charset='utf-8'><title>Reports for {html.escape(coder)}"
                                       f"</title><style>{CSS}</style><h1>Reports for {html.escape(coder)}</h1>"
                                       f"<p>Code them in this order, one row each in coding_sheet_{html.escape(coder)}"
                                       f".xlsx.</p><ol>{idx}</ol>", encoding="utf-8")
        with zipfile.ZipFile(OUT / "packets" / f"{coder}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(pk.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(OUT / "packets"))
        print(f"{coder}: {len(mine)} reports, {len(my_claims)} gene claims -> manual_coding/packets/{coder}.zip")
    (OUT / "returned").mkdir(exist_ok=True)
    if not protocol.exists():
        print("note: manual_coding/protocol.docx not found; run scripts/manual_coding_protocol.py, then rerun")


if __name__ == "__main__":
    main()
