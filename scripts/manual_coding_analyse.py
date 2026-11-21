"""Analyse the manual coding: agreement between human coders, adjudication, agreement of each language model with
the human consensus, and the main results recomputed with the human coding.

Steps:
1. Coders return manual_coding/returned/coding_sheet_<coder>.xlsx.
2. Run this script. It reports completeness and agreement between coders (Fleiss' kappa, two ratings per report)
   and writes manual_coding/adjudication.xlsx with every disagreement.
3. The two coders of each report fill the 'Consensus' column without the key and save the file as
   manual_coding/returned/adjudication.xlsx.
4. Run this script again. With every disagreement resolved, it compares the human consensus with each language
   model (Cohen's kappa), names the model that agrees best, and recomputes the headline results.

Outputs: manual_coding/results/summary.json and summary.md.
Usage: python -I scripts/manual_coding_analyse.py [--returned DIR] [--out DIR]
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

MA = Path(__file__).resolve().parents[1]
MC = MA / "manual_coding"
MODELS = {"tencent_hy4-flash": "Tencent HY4 Flash (rater)", "deepseek_deepseek-v4.1-flash-1017": "DeepSeek V4.1 Flash"}
ITEMS = [("Reports a difference", "reports_difference"), ("Acidification conclusion", "acidification"),
         ("C1 compares AT8 vs MAP2", "C1"), ("C2 two or more proteostasis arms", "C2"),
         ("C3 addresses lysosomal acidification", "C3"), ("FDR multiple-testing correction", "FDR"),
         ("Donor-aware (8 donors as n)", "donor_aware")]
CRIT = ["C1", "C2", "C3", "FDR", "donor_aware"]
ACID = {"impaired": "impaired", "compensated": "compensated", "altered_other": "altered otherwise",
        "unchanged": "unchanged", "not_addressed": "not addressed"}


def norm(v):
    return str(v).strip().lower() if v not in (None, "") else None


def read_sheets(returned):
    coding, claims = {}, {}
    for f in sorted(returned.glob("coding_sheet_*.xlsx")):
        coder = f.stem.replace("coding_sheet_", "")
        wb = load_workbook(f, data_only=True)
        ws = wb["Coding"]
        head = [c.value for c in ws[1]]
        col = {h: i for i, h in enumerate(head)}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0]:
                coding[(row[0], coder)] = {k: norm(row[col[h]]) for h, k in ITEMS}
                coding[(row[0], coder)]["_note"] = row[col["Evidence or doubts"]]
        if "Gene claims" in wb.sheetnames:
            for row in wb["Gene claims"].iter_rows(min_row=2, values_only=True):
                if row[0]:
                    claims[(row[0], coder)] = norm(row[5])
    return coding, claims


def fleiss_two(pairs):
    """Fleiss' kappa with two ratings per subject (raters may differ between subjects)."""
    n = len(pairs)
    if not n:
        return None
    cats = sorted({x for p in pairs for x in p})
    p_bar = sum(a == b for a, b in pairs) / n        # with two ratings, a subject's agreement is 1 or 0
    pj = {c: sum((a == c) + (b == c) for a, b in pairs) / (2 * n) for c in cats}
    pe = sum(v * v for v in pj.values())
    return round((p_bar - pe) / (1 - pe), 2) if pe < 1 else "n/a (one category)"


def cohen(pairs):
    n = len(pairs)
    if not n:
        return None, None
    po = sum(a == b for a, b in pairs) / n
    cats = {x for p in pairs for x in p}
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n) for c in cats)
    return (round((po - pe) / (1 - pe), 2) if pe < 1 else "n/a (one category)"), round(100 * po)


def model_codes(label, model):
    out = {}
    for task in ("verdict", "checklist"):
        f = MA / "runs/audit" / task / model / f"{label}.json"
        if f.exists():
            a = json.loads(f.read_text())
            if task == "verdict":
                out["reports_difference"] = "yes" if a.get("reports_difference") else "no"
                out["acidification"] = ACID.get(a.get("acidification"), a.get("acidification"))
            else:
                out.update({c: "yes" if a.get(c) else "no" for c in CRIT})
    return out


def style(ws, widths):
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = w
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="E8E8E8")
        c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--returned", type=Path, default=MC / "returned")
    ap.add_argument("--out", type=Path, default=MC / "results")
    ap.add_argument("--work", type=Path, default=MC, help="where the adjudication sheet to fill is written")
    args = ap.parse_args()
    key = {r["rid"]: r for r in csv.DictReader(open(MC / "key.csv"))}
    ckey = {r["claim_id"]: r for r in csv.DictReader(open(MC / "claims_key.csv"))}
    coding, claims = read_sheets(args.returned)
    coders = sorted({c for _, c in coding})
    lines, S = [], {"coders": coders}
    lines.append(f"# Manual coding: results\n\nSheets returned: {', '.join(coders) or 'none'}\n")

    # ------------------------------------------------ completeness
    missing = Counter()
    for (rid, coder), v in coding.items():
        missing[coder] += sum(v[k] is None for _, k in ITEMS)
    expected = Counter(c for r in key.values() for c in (r["coder_1"], r["coder_2"]))
    lines.append("## Completeness\n")
    for c in coders:
        done = sum(1 for (rid, cc), v in coding.items() if cc == c and all(v[k] for _, k in ITEMS))
        lines.append(f"- {c}: {done} of {expected[c]} reports fully coded, {missing[c]} empty answer cells")
    S["completeness"] = {c: {"expected": expected[c], "empty_cells": missing[c]} for c in coders}

    # ------------------------------------------------ agreement between human coders
    both = [rid for rid, r in key.items() if (rid, r["coder_1"]) in coding and (rid, r["coder_2"]) in coding]
    lines.append(f"\n## Agreement between human coders ({len(both)} reports coded twice)\n")
    lines.append("| Item | Agreement | Fleiss' κ |\n|---|---|---|")
    S["human_agreement"], disagreements = {}, []
    for h, k in ITEMS:
        pairs = [(coding[(rid, key[rid]["coder_1"])][k], coding[(rid, key[rid]["coder_2"])][k]) for rid in both]
        pairs = [p for p in pairs if None not in p]
        agree = sum(a == b for a, b in pairs)
        kap = fleiss_two(pairs)
        S["human_agreement"][k] = {"n": len(pairs), "agree": agree, "fleiss_kappa": kap}
        lines.append(f"| {h} | {agree}/{len(pairs)} | {kap} |")
        for rid in both:
            a, b = coding[(rid, key[rid]["coder_1"])][k], coding[(rid, key[rid]["coder_2"])][k]
            if a != b:
                disagreements.append((rid, h, k, key[rid]["coder_1"], a, key[rid]["coder_2"], b,
                                      coding[(rid, key[rid]["coder_1"])]["_note"],
                                      coding[(rid, key[rid]["coder_2"])]["_note"]))

    # ------------------------------------------------ adjudication
    adj_in = args.returned / "adjudication.xlsx"
    resolved = {}
    if adj_in.exists():
        ws = load_workbook(adj_in, data_only=True)["Adjudication"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] and norm(row[6]):
                resolved[(row[0], row[1])] = norm(row[6])
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Adjudication"
        ws.append(["Report", "Item", "Coder A", "Answer A", "Coder B", "Answer B", "Consensus", "Note A", "Note B"])
        allowed = {"reports_difference": "yes,no", "acidification":
                   "impaired,compensated,altered otherwise,unchanged,not addressed"}
        for rid, h, k, ca, a, cb, b, na, nb in sorted(disagreements):
            ws.append([rid, h, ca, a, cb, b, None, na, nb])
            dv = DataValidation(type="list", formula1='"' + allowed.get(k, "yes,no") + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"G{ws.max_row}")
        style(ws, [9, 30, 9, 16, 9, 16, 16, 40, 40])
        if disagreements:
            wb.save(args.work / "adjudication.xlsx")
    item_of = {h: k for h, k in ITEMS}
    unresolved = [d for d in disagreements if (d[0], d[1]) not in resolved]
    lines.append(f"\n## Adjudication\n\n{len(disagreements)} disagreements, {len(disagreements) - len(unresolved)} "
                 f"resolved." + ("" if adj_in.exists() or not disagreements else
                                 f" Fill {args.work / 'adjudication.xlsx'} and save it in {args.returned}."))
    S["disagreements"], S["unresolved"] = len(disagreements), len(unresolved)

    consensus = {}
    for rid in both:
        c = {}
        for h, k in ITEMS:
            a, b = coding[(rid, key[rid]["coder_1"])][k], coding[(rid, key[rid]["coder_2"])][k]
            c[k] = a if a == b else resolved.get((rid, h))
        consensus[rid] = c
    complete = {rid: c for rid, c in consensus.items() if all(c[k] for _, k in ITEMS)}
    if unresolved or len(complete) < len(key):
        lines.append(f"\nConsensus available for {len(complete)} of {len(key)} reports. The comparison with the "
                     f"language models and the recomputed results wait until every report is coded twice and every "
                     f"disagreement is resolved, because the agreed reports alone are the easy ones.")
        complete = {}

    # ------------------------------------------------ models against the human consensus
    lines.append(f"\n## Language models against the human consensus ({len(complete)} reports)\n")
    lines.append("| Item | " + " | ".join(f"{v}: κ (agreement)" for v in MODELS.values()) + " |\n|---|---|---|")
    S["models"] = {m: {} for m in MODELS}
    mc = {rid: {m: model_codes(key[rid]["label"], m) for m in MODELS} for rid in complete}
    for h, k in ITEMS:
        cells = []
        for m in MODELS:
            pairs = [(complete[rid][k], mc[rid][m].get(k)) for rid in complete if mc[rid][m].get(k)]
            kap, po = cohen(pairs)
            S["models"][m][k] = {"kappa": kap, "agreement_pct": po, "n": len(pairs)}
            cells.append(f"{kap} ({po}%)")
        lines.append(f"| {h} | " + " | ".join(cells) + " |")
    pooled = {}
    for m in MODELS:
        pairs = [(complete[rid][k], mc[rid][m].get(k)) for rid in complete for _, k in ITEMS if mc[rid][m].get(k)]
        pooled[m] = cohen(pairs)[0]
        S["models"][m]["pooled_kappa"] = pooled[m]
    if complete and all(isinstance(v, float) for v in pooled.values()):
        best = max(pooled, key=pooled.get)
        S["best_model"] = best
        lines.append(f"\nPooled over the seven items: " + ", ".join(f"{MODELS[m]} κ = {pooled[m]}" for m in MODELS) +
                     f". Closest to the human consensus: {MODELS[best]}.")

    # ------------------------------------------------ headline results, human consensus against the rater
    lines.append("\n## Main results with the human consensus (rater in brackets)\n")
    lines.append("| Condition, model | n | Reports a difference | Meets all five criteria | FDR claimed | Impaired | "
                 "Compensated |\n|---|---|---|---|---|---|---|")
    S["results"] = {}
    rater = next(iter(MODELS))
    for cond in ("real", "shuffled", "planted"):
        for model in ("GLM 5.2", "Opus 4.8"):
            rids = [rid for rid in complete if key[rid]["condition"] == cond and key[rid]["model"] == model]
            if not rids:
                continue

            def count(src, test):
                return sum(test(src(rid)) for rid in rids)

            hum = lambda rid: complete[rid]
            mod = lambda rid: mc[rid][rater]
            row = {}
            for name, test in (("difference", lambda c: c.get("reports_difference") == "yes"),
                               ("all_five", lambda c: all(c.get(x) == "yes" for x in CRIT)),
                               ("fdr", lambda c: c.get("FDR") == "yes"),
                               ("impaired", lambda c: c.get("acidification") == "impaired"),
                               ("compensated", lambda c: c.get("acidification") == "compensated")):
                row[name] = (count(hum, test), count(mod, test))
            S["results"][f"{cond}|{model}"] = {"n": len(rids), **{k: {"human": a, "rater": b} for k, (a, b) in row.items()}}
            lines.append(f"| {cond}, {model} | {len(rids)} | " +
                         " | ".join(f"{a} ({b})" for a, b in row.values()) + " |")

    # ------------------------------------------------ gene claims
    by_claim = defaultdict(dict)
    for (cid, coder), v in claims.items():
        if v:
            by_claim[cid][coder] = v
    two = {cid: list(v.values()) for cid, v in by_claim.items() if len(v) == 2}
    if two:
        agree = sum(a == b for a, b in two.values())
        conf = {cid: v[0] for cid, v in two.items() if v[0] == v[1]}
        lines.append(f"\n## Gene claims extracted by the rater\n\n{len(two)} claims checked twice, coders agreed on "
                     f"{agree}. Among agreed checks:")
        S["gene_claims"] = {"checked_twice": len(two), "agree": agree}
        for cond in ("real", "shuffled", "planted"):
            ids = [cid for cid in conf if key[ckey[cid]["rid"]]["condition"] == cond]
            if ids:
                ok = sum(conf[cid] == "yes" for cid in ids)
                lines.append(f"- {cond}: {ok} of {len(ids)} confirmed as stated ({round(100 * ok / len(ids))}%)")
                S["gene_claims"][cond] = {"confirmed": ok, "n": len(ids)}

    if not complete:                       # drop the empty model and results sections until adjudication is done
        i = next(i for i, x in enumerate(lines) if x.startswith("\n## Language models"))
        j = next((i2 for i2, x in enumerate(lines) if x.startswith("\n## Gene claims")), len(lines))
        del lines[i:j]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(S, indent=1))
    (args.out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
