"""Summaries of the report audit (runs/audit/<task>/<coder>/*.json): checklist, gene claims, post hoc sets.

Gene claims are compared with the reference analysis of the data each report analysed (real labels, or the shuffle
it received): supported = DESeq2 padj < 0.05 in the claimed direction; contradicted = padj < 0.05 the other way;
not supported = padj >= 0.05; not testable = gene filtered out or absent. The paired t-test is reported alongside.

Usage: .venv/bin/python scripts/audit_summary.py [checklist|genes|posthoc|all]
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

MA = Path(__file__).resolve().parents[1]
AUD = MA / "runs/audit"
REF = MA / "runs/reference_de"
ORDER = ["Opus 4.8", "Kimi K3", "GLM 5.2", "main case study 3 report", "GLM 5.2 (ours)", "Opus 4.8 (ours)"]
MECH = ("ATP6V", "ATP6AP", "TMEM175", "MCOLN", "TPCN", "CLCN7", "OSTM1", "SLC26A11", "SLC12A9")


def load(task):
    out = defaultdict(dict)                     # coder -> label -> answer
    for d in sorted((AUD / task).glob("*")):
        for f in d.glob("*.json"):
            out[d.name][f.stem] = json.loads(f.read_text())
    return out


def group(ans):
    m = ans.get("_meta", {})
    return f"{m.get('config')} [{m.get('labels')}]"


def checklist():
    data = load("checklist")
    crit = ["C1", "C2", "C3", "FDR", "donor_aware"]
    print("\n### Extended Data Table 2 criteria, as coded (runs meeting each criterion / runs)")
    print("paper's own GLM 5.2 online row: 10 10 10 8 10; Opus 4.8 and Kimi K3: 10 on all five")
    for coder, answers in data.items():
        print(f"\n coder {coder}")
        groups = defaultdict(list)
        for a in answers.values():
            if "_error" not in a:
                groups[group(a)].append(a)
        for g in sorted(groups, key=lambda x: (ORDER.index(x.split(" [")[0]) if x.split(" [")[0] in ORDER else 9, x)):
            A = groups[g]
            print(f"  {g:36s} n={len(A):2d}  " + "  ".join(f"{c} {sum(bool(a.get(c)) for a in A)}" for c in crit))
    print("\n acidification conclusions of our shuffled runs (first coder):")
    first = next(iter(data.values()))
    for lab, a in sorted(first.items()):
        if a.get("_meta", {}).get("labels") in ("shuffled", "planted") or lab in ("run0", "opus_cs3_original"):
            print(f"  {lab:20s} {a.get('acidification_conclusion', '')[:220]}")


def ref_tables():
    tabs = {}
    planted = [f"planted{k}" for k in range(21, 31) if (REF / f"deseq2_planted{k}.csv").exists()]
    for name in ["real"] + planted + [f"shuffle{k}" for k in range(1, 11)]:
        d = {r[""]: r for r in csv.DictReader(open(REF / f"deseq2_{name}.csv"))}
        t = {r["gene"]: r for r in csv.DictReader(open(REF / f"de_{name}.csv"))}
        tabs[name] = (d, t)
    return tabs


def verdict(gene, direction, ref):
    d, _ = ref
    r = d.get(gene)
    if r is None or not r.get("padj"):
        return "not testable"
    padj, lfc = float(r["padj"]), float(r["log2FoldChange"])
    if direction == "unchanged":
        return "agrees (unchanged)" if padj >= 0.05 else "contradicted (changed)"
    if padj >= 0.05:
        return "not supported"
    return "supported" if (lfc > 0) == (direction == "up") else "contradicted"


def genes():
    data = load("genes")
    tabs = ref_tables()
    rows = []
    for coder, answers in data.items():
        for lab, a in answers.items():
            if "_error" in a:
                continue
            ref = tabs[a["_meta"]["reference"]]
            seen = set()
            for g in a.get("genes") or []:
                sym = str(g.get("gene", "")).strip().upper()
                if not sym or sym in seen:
                    continue
                seen.add(sym)
                v = verdict(sym, g.get("direction"), ref)
                tt = ref[1].get(sym)
                rows.append({"coder": coder, "label": lab, "group": group(a), "gene": sym, "direction": g.get("direction"),
                             "in_summary": bool(g.get("in_summary")), "mechanism_gene": sym.startswith(MECH),
                             "verdict": v, "deseq2_padj": (ref[0].get(sym) or {}).get("padj", ""),
                             "ttest_fdr": tt["fdr_bh"] if tt else "", "statistic_cited": g.get("statistic", ""),
                             "quote": str(g.get("quote", ""))[:200]})
    out = AUD / "gene_claims_scored.csv"
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"\n### Directional gene claims vs the corrected reference (DESeq2 padj < 0.05), written to {out.name}")
    for coder in data:
        print(f"\n coder {coder}")
        for scope, keep in (("all claimed genes", lambda r: True), ("genes in the summary", lambda r: r["in_summary"]),
                            ("acidification mechanism genes", lambda r: r["mechanism_gene"])):
            print(f"  -- {scope}")
            agg = defaultdict(lambda: defaultdict(int))
            for r in rows:
                if r["coder"] == coder and r["direction"] != "unchanged" and keep(r):
                    agg[r["group"]][r["verdict"]] += 1
            for g in sorted(agg, key=lambda x: (ORDER.index(x.split(" [")[0]) if x.split(" [")[0] in ORDER else 9, x)):
                c = agg[g]; n = sum(c.values()); s = c["supported"]
                print(f"   {g:36s} claims {n:4d}  supported {s:4d} ({100 * s / n:3.0f}%)  not supported {c['not supported']:4d}  "
                      f"contradicted {c['contradicted']:3d}  not testable {c['not testable']:3d}")
    print("\n TMEM175 / MCOLN claims (first coder):")
    first = next(iter(data))
    for r in rows:
        if r["coder"] == first and r["gene"].startswith(("TMEM175", "MCOLN")) and r["direction"] != "unchanged":
            print(f"   {r['label']:26s} {r['gene']:8s} {r['direction']:5s} {r['verdict']:14s} cited: {r['statistic_cited'][:60]}")


def posthoc():
    data = load("posthoc")
    print("\n### Gene sets assembled from the run's own top hits")
    for coder, answers in data.items():
        print(f"\n coder {coder}")
        groups = defaultdict(list)
        for a in answers.values():
            if "_error" not in a:
                groups[group(a)].append(a)
        for g in sorted(groups, key=lambda x: (ORDER.index(x.split(" [")[0]) if x.split(" [")[0] in ORDER else 9, x)):
            A = groups[g]
            yes = [a for a in A if a.get("post_hoc_set") == "yes"]
            fam = sum(a.get("correction_scope") == "chosen_family_only" for a in yes)
            none = sum(a.get("correction_scope") == "none" for a in yes)
            print(f"  {g:36s} n={len(A):2d}  post hoc set: {len(yes):2d} (presented as finding {sum(bool(a.get('presented_as_finding')) for a in yes)}; "
                  f"corrected only within chosen family {fam}, uncorrected {none}); unclear {sum(a.get('post_hoc_set') == 'unclear' for a in A)}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("checklist", checklist), ("genes", genes), ("posthoc", posthoc)):
        if which in (name, "all") and (AUD / name).exists():
            fn()
