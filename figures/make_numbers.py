"""Numbers for the case study 3 controls, read from the result files (never retyped).

Writes numbers.tex (LaTeX macros) and numbers.json next to this script.
Sources: runs/reference_de/{de,deseq2}_{real,shuffle1..3}.csv, runs/audit/checklist/*/*.json,
runs/ma1_null_s*/artifacts/final_report.md, data/null_seed2.h5ad (module test).
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

MA = Path(__file__).resolve().parents[1]
REF = MA / "runs/reference_de"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(MA / "scripts"))

N = {}

# One rater codes the reports. Tencent HY4 Flash was chosen provisionally because its coding of the authors' 30
# benchmark reports reproduced their published Extended Data Table 2 scores exactly (DeepSeek V4.1 Flash: off by
# one run). The final rater will be the model with the higher kappa against B.L.G.'s hand coding of a sample.
RATER = "tencent_hy4-flash"
SECOND = "deepseek_deepseek-v4.1-flash-1017"


def put(name, value):
    N[name] = value


def fmt_int(x):
    return f"{int(x):,}"


# ---------------------------------------------------------------- reference analyses
SHUFFLES = [f"shuffle{k}" for k in range(1, 11)]
PLANTED = [f"planted{k}" for k in range(21, 31) if (REF / f"deseq2_planted{k}.csv").exists()]
PLANTED_GENES = {"TMEM175", "MCOLN1", "TPCN1", "TPCN2"}
for name in ["real"] + SHUFFLES + PLANTED:
    t = list(csv.DictReader(open(REF / f"de_{name}.csv")))
    d = list(csv.DictReader(open(REF / f"deseq2_{name}.csv")))
    tq = np.array([float(r["fdr_bh"]) for r in t]); tp = np.array([float(r["p"]) for r in t])
    dq = np.array([float(r["padj"]) if r["padj"] else 1.0 for r in d]); dp = np.array([float(r["pvalue"]) if r["pvalue"] else 1.0 for r in d])
    put(f"{name}_t_genes", len(t)); put(f"{name}_t_fdr05", int((tq < 0.05).sum())); put(f"{name}_t_nom05", int((tp < 0.05).sum()))
    put(f"{name}_d_genes", len(d)); put(f"{name}_d_fdr05", int((dq < 0.05).sum())); put(f"{name}_d_nom05", int((dp < 0.05).sum()))
    put(f"{name}_t_minq", float(tq.min())); put(f"{name}_d_minq", float(dq.min()))
put("real_t_pct", round(100 * N["real_t_fdr05"] / N["real_t_genes"]))
put("real_d_pct", round(100 * N["real_d_fdr05"] / N["real_d_genes"]))
put("n_shuffles", len(SHUFFLES))
put("shuffle_t_nom_min", min(N[f"{s}_t_nom05"] for s in SHUFFLES))
put("shuffle_t_nom_max", max(N[f"{s}_t_nom05"] for s in SHUFFLES))
put("shuffle_t_expected", round(0.05 * np.mean([N[f"{s}_t_genes"] for s in SHUFFLES])))
put("shuffle_t_minq_all", min(N[f"{s}_t_minq"] for s in SHUFFLES))
put("shuffle_fdr05_max", max(max(N[f"{s}_t_fdr05"], N[f"{s}_d_fdr05"]) for s in SHUFFLES))

# planted copies: recovery of the four planted genes after correction, and anything else flagged
rec_d = rec_t = other_d = other_t = 0
for name in PLANTED:
    d = {r[""]: r for r in csv.DictReader(open(REF / f"deseq2_{name}.csv"))}
    t = {r["gene"]: r for r in csv.DictReader(open(REF / f"de_{name}.csv"))}
    sig_d = {g for g, r in d.items() if r["padj"] and float(r["padj"]) < 0.05}
    sig_t = {g for g, r in t.items() if float(r["fdr_bh"]) < 0.05}
    rec_d += len(sig_d & PLANTED_GENES); rec_t += len(sig_t & PLANTED_GENES)
    other_d += len(sig_d - PLANTED_GENES); other_t += len(sig_t - PLANTED_GENES)
    put(f"{name}_planted_max_padj", max(float(d[g]["padj"]) for g in PLANTED_GENES))
    put(f"{name}_planted_lfc_min", min(float(d[g]["log2FoldChange"]) for g in PLANTED_GENES))
put("planted_n_tests", len(PLANTED) * len(PLANTED_GENES))
put("planted_rec_d", rec_d); put("planted_rec_t", rec_t); put("planted_other_d", other_d); put("planted_other_t", other_t)
put("planted_max_padj", max(N[f"{n}_planted_max_padj"] for n in PLANTED))
put("planted_min_padj", min(float(r["padj"]) for n in PLANTED for r in csv.DictReader(open(REF / f"deseq2_{n}.csv"))
                            if r[""] in PLANTED_GENES))

# real-data mechanism genes (DESeq2)
d_real = {r[""]: r for r in csv.DictReader(open(REF / "deseq2_real.csv"))}
t_real = {r["gene"]: r for r in csv.DictReader(open(REF / "de_real.csv"))}
for g in ("ATP6V1B2", "ATP6AP2", "ATP6V1H", "TMEM175", "MCOLN1", "TPCN1", "TPCN2", "CLCN7"):
    put(f"real_{g}_padj", float(d_real[g]["padj"])); put(f"real_{g}_lfc", float(d_real[g]["log2FoldChange"]))
    if g in t_real:
        put(f"real_{g}_tp", float(t_real[g]["p"])); put(f"real_{g}_tq", float(t_real[g]["fdr_bh"]))

# ---------------------------------------------------------------- run verdicts (two coders)
def coded(task, coders=(RATER,)):
    out = {}
    for d in sorted((MA / "runs/audit" / task).glob("*")):
        if d.name not in coders:
            continue
        for f in d.glob("*.json"):
            a = json.loads(f.read_text())
            if "_error" not in a:
                out.setdefault(f.stem, {})[d.name] = a
    return out


V = coded("verdict")
MODELS = {"glm": "ma1_null", "opus": "opus_null"}


def pick(prefix, k):                 # the completed run for this model and shuffle (a resubmission ends in b)
    for lab in (f"{prefix}_s{k}b", f"{prefix}_s{k}"):
        if lab in V:
            return lab
    return None


def agreed(lab, field):
    vals = {json.dumps(a.get(field)) for a in V[lab].values()}
    return json.loads(vals.pop()) if len(vals) == 1 else "disagree"


runs = []                             # one row per shuffled run
for m, prefix in MODELS.items():
    for k in range(1, 11):
        lab = pick(prefix, k)
        if lab:
            runs.append({"model": m, "seed": k, "label": lab, "difference": agreed(lab, "reports_difference"),
                         "acidification": agreed(lab, "acidification")})
from scipy.stats import beta as _beta  # noqa: E402


def cp(k, n):
    lo = _beta.ppf(0.025, k, n - k + 1) if k else 0.0
    hi = _beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return round(100 * lo), round(100 * hi)


disagreements = [r["label"] for r in runs if "disagree" in (r["difference"], r["acidification"])]
for m in list(MODELS) + ["all"]:
    R = [r for r in runs if m == "all" or r["model"] == m]
    k = sum(r["difference"] is True for r in R)
    put(f"{m}_shuf_n", len(R)); put(f"{m}_shuf_fp", k); put(f"{m}_shuf_null", sum(r["difference"] is False for r in R))
    put(f"{m}_shuf_impaired", sum(r["acidification"] == "impaired" for r in R))
    put(f"{m}_shuf_compensated", sum(r["acidification"] == "compensated" for r in R))
    put(f"{m}_shuf_unchanged", sum(r["acidification"] == "unchanged" for r in R))
    # runs that found acidification unchanged yet still presented another tangle-associated difference
    put(f"{m}_shuf_unchanged_fp", sum(r["acidification"] == "unchanged" and r["difference"] is True for r in R))
    lo, hi = cp(k, len(R)) if R else (0, 0)
    put(f"{m}_shuf_ci_lo", lo); put(f"{m}_shuf_ci_hi", hi)
seeds_both = sorted({r["seed"] for r in runs if r["model"] == "glm"} & {r["seed"] for r in runs if r["model"] == "opus"})
by = {(r["model"], r["seed"]): r["difference"] for r in runs}
put("paired_n", len(seeds_both))
put("paired_both", sum(by[("glm", k)] is True and by[("opus", k)] is True for k in seeds_both))
put("paired_neither", sum(by[("glm", k)] is False and by[("opus", k)] is False for k in seeds_both))
PLANT_PREFIX = {"glm": "glm_planted", "opus": "opus_planted"}
plant_runs = {m: [lab for k in range(21, 31) if (lab := pick(p, k))] for m, p in PLANT_PREFIX.items()}
plant_runs["all"] = plant_runs["glm"] + plant_runs["opus"]
for m, labs in plant_runs.items():
    put(f"{m}_plant_n", len(labs))
    put(f"{m}_plant_mech", sum(agreed(lab, "reports_difference") is True for lab in labs))
    for a in ("impaired", "compensated", "unchanged", "altered_other"):
        put(f"{m}_plant_{a.replace('_', '')}", sum(agreed(lab, "acidification") == a for lab in labs))

# genes the conclusions of the shuffled runs rest on, in the reference analysis of the same copy
lead_rows = []
for r in runs:
    if r["difference"] is not True:
        continue
    t = {x["gene"]: x for x in csv.DictReader(open(REF / f"de_shuffle{r['seed']}.csv"))}
    d = {x[""]: x for x in csv.DictReader(open(REF / f"deseq2_shuffle{r['seed']}.csv"))}
    genes = sorted({str(g).strip().upper() for a in V[r["label"]].values() for g in a.get("main_genes") or []})
    for g in genes:
        lead_rows.append({"label": r["label"], "model": r["model"], "seed": r["seed"], "gene": g,
                          "t_p": float(t[g]["p"]) if g in t else None,
                          "t_fdr": float(t[g]["fdr_bh"]) if g in t else None,
                          "deseq2_padj": float(d[g]["padj"]) if g in d and d[g]["padj"] else None})
tested = [x for x in lead_rows if x["t_fdr"] is not None or x["deseq2_padj"] is not None]
put("lead_n", len({(x["label"], x["gene"]) for x in tested}))
put("lead_min_t_fdr", min(x["t_fdr"] for x in tested if x["t_fdr"] is not None))
put("lead_min_d_padj", min(x["deseq2_padj"] for x in tested if x["deseq2_padj"] is not None))
put("lead_min_t_p", min(x["t_p"] for x in tested if x["t_p"] is not None))
put("lead_min_d_padj_floor", f"{np.floor(100 * N['lead_min_d_padj']) / 100:.2f}")
put("lead_min_t_fdr_floor", f"{np.floor(100 * N['lead_min_t_fdr']) / 100:.2f}")

# seed 2 'chloride module' (SLC26A11 + SLC12A9), paired donor-level test, as the run tested it
import h5py  # noqa: E402
from scipy import sparse, stats  # noqa: E402
from reference_de import col  # noqa: E402
f = h5py.File(MA / "data/null_seed2.h5ad", "r"); raw = f["raw"]["X"]
X = sparse.csr_matrix((raw["data"][:], raw["indices"][:], raw["indptr"][:]), shape=tuple(raw.attrs["shape"]))
var = f["raw"]["var"] if "feature_name" in f["raw"]["var"] else f["var"]
genes = list(col(var, "feature_name")); lab, don = col(f["obs"], "SORT"), col(f["obs"], "donor_id")
samples = [(dd, l) for dd in sorted(set(don)) for l in ("AT8", "MAP2")]
ind = sparse.csr_matrix(np.array([(don == dd) & (lab == l) for dd, l in samples], dtype=np.float32))
pb = np.asarray((ind @ X).todense()); cpm = pb / pb.sum(1, keepdims=True) * 1e6
idx = [genes.index("SLC26A11"), genes.index("SLC12A9")]
score = (np.log2(cpm[0::2][:, idx] + 1) - np.log2(cpm[1::2][:, idx] + 1)).mean(1)
put("module_p", float(stats.ttest_1samp(score, 0).pvalue))
put("module_donors_same_sign", int((np.sign(score) == np.sign(score.mean())).sum()))
t2 = {r["gene"]: r for r in csv.DictReader(open(REF / "de_shuffle2.csv"))}
put("slc26a11_tq", float(t2["SLC26A11"]["fdr_bh"])); put("slc26a11_tp", float(t2["SLC26A11"]["p"]))

# ---------------------------------------------------------------- checklist (Extended Data Table 2), two coders
crit = ["C1", "C2", "C3", "FDR", "donor_aware"]
chk = {}
for coder_dir in [MA / "runs/audit/checklist" / RATER]:
    rows = [json.loads(p.read_text()) for p in coder_dir.glob("*.json")]
    chosen = {r["label"] for r in runs}
    for grp, keep in (("authors_glm", lambda m: m["config"] == "GLM 5.2"),
                      ("ours_shuffled_glm", lambda m: m["label"] in chosen and "GLM" in m["config"]),
                      ("ours_shuffled_opus", lambda m: m["label"] in chosen and "Opus" in m["config"])):
        R = [r for r in rows if "_error" not in r and keep(r["_meta"])]
        chk.setdefault(grp, {})[coder_dir.name] = {c: sum(bool(r.get(c)) for r in R) for c in crit} | {"n": len(R)}
CH = coded("checklist")
core, fdr = [], []
for c in sorted({c for v in CH.values() for c in v}):
    R = [CH[r["label"]][c] for r in runs if r["label"] in CH and c in CH[r["label"]]]
    core.append(sum(all(bool(a.get(k)) for k in ("C1", "C2", "C3", "donor_aware")) for a in R))
    fdr.append(sum(bool(a.get("FDR")) for a in R))
put("chk_shuf_core", min(core)); put("chk_shuf_fdr_lo", min(fdr)); put("chk_shuf_fdr_hi", max(fdr))
# shuffled runs meeting all five criteria (rater), and run-level specificity (share concluding no difference)
put("all_shuf_pass_all", sum(all(bool(CH[r["label"]][RATER].get(c)) for c in crit) for r in runs))
put("all_shuf_spec_pct", round(100 * N["all_shuf_null"] / N["all_shuf_n"]))
for grp, by_coder in chk.items():
    for c in crit + ["n"]:
        vals = sorted({v[c] for v in by_coder.values()})
        put(f"chk_{grp}_{c}", vals[0] if len(vals) == 1 else f"{vals[0]}--{vals[-1]}")

# ---------------------------------------------------------------- gene claims vs the reference (audit_summary.py genes)
G = list(csv.DictReader(open(MA / "runs/audit/gene_claims_scored.csv")))
G = [g for g in G if g["direction"] != "unchanged" and g["coder"] == RATER]
coders = sorted({g["coder"] for g in G})


def share(keep):
    out = []
    for c in coders:
        R = [g for g in G if g["coder"] == c and keep(g)]
        out.append((sum(g["verdict"] == "supported" for g in R), len(R)))
    return out


authors_pct = [100 * k / n for cfg in ("Opus 4.8 [real]", "Kimi K3 [real]", "GLM 5.2 [real]")
               for k, n in share(lambda g, cfg=cfg: g["group"] == cfg)]
put("genes_authors_pct_lo", round(min(authors_pct))); put("genes_authors_pct_hi", round(max(authors_pct)))
chosen = {r["label"] for r in runs}
sh = share(lambda g: g["label"] in chosen)
put("genes_shuf_supported", max(k for k, _ in sh)); put("genes_shuf_n_lo", min(n for _, n in sh)); put("genes_shuf_n_hi", max(n for _, n in sh))
# planted runs: planted genes claimed in the planted direction (up), claims about any other gene, checklist flags
for m, labs in plant_runs.items():
    up = {lab: {g["gene"] for g in G if g["label"] == lab and g["gene"] in PLANTED_GENES and g["direction"] == "up"}
          for lab in labs}
    other = [g for g in G if g["label"] in labs and g["gene"] not in PLANTED_GENES]
    per_run = [sum(1 for g in other if g["label"] == lab) for lab in labs]
    found = sum(len(v) for v in up.values())
    put(f"{m}_plant_found", found); put(f"{m}_plant_of", 4 * len(labs))
    put(f"{m}_plant_found_pct", round(100 * found / (4 * len(labs))))
    put(f"{m}_plant_all4", sum(len(v) == 4 for v in up.values()))
    put(f"{m}_plant_found_min", min(len(v) for v in up.values()))
    put(f"{m}_plant_wrong_dir", sum(1 for g in G if g["label"] in labs and g["gene"] in PLANTED_GENES
                                    and g["direction"] == "down"))
    put(f"{m}_plant_other", len(other)); put(f"{m}_plant_other_supported", sum(g["verdict"] == "supported" for g in other))
    put(f"{m}_plant_other_min", min(per_run)); put(f"{m}_plant_other_max", max(per_run))
    put(f"{m}_plant_other_median", int(np.median(per_run)))
    put(f"{m}_plant_true_pct", round(100 * found / (found + len(other))))   # share of directional claims that are true
    put(f"{m}_plant_flagged", sum(not all(bool(CH[lab][RATER].get(c)) for c in crit) for lab in labs))
put("planted_rec_d_pct", round(100 * N["planted_rec_d"] / N["planted_n_tests"]))
put("planted_rec_t_pct", round(100 * N["planted_rec_t"] / N["planted_n_tests"]))
real_ours = {"run0", "opus_cs3_original"}
ro = share(lambda g: g["label"] in real_ours)
put("genes_ours_real_pct_lo", round(min(100 * k / n for k, n in ro))); put("genes_ours_real_pct_hi", round(max(100 * k / n for k, n in ro)))

# single-rater numbers for the text
put("chk_shuf_fdr", N["chk_shuf_fdr_lo"])
per_report = [sum(1 for g in G if g["label"] == lab) for lab in chosen]
put("genes_shuf_per_report_min", min(per_report)); put("genes_shuf_per_report_max", max(per_report))
authors_labels = {g["label"] for g in G if g["group"] in ("Opus 4.8 [real]", "Kimi K3 [real]", "GLM 5.2 [real]")}
per_report_real = [sum(1 for g in G if g["label"] == lab) for lab in authors_labels]
put("genes_authors_per_report_min", min(per_report_real)); put("genes_authors_per_report_max", max(per_report_real))
put("genes_authors_per_report_median", int(np.median(per_report_real)))
put("genes_shuf_per_report_median", int(np.median(per_report)))
put("genes_shuf_n", N["genes_shuf_n_lo"])
put("genes_ours_real_pct", N["genes_ours_real_pct_lo"])

# agreement between the rater and a second model that coded every report independently (Cohen's kappa)
def kappa(pairs):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    cats = {x for p in pairs for x in p}
    pe = sum((sum(a == k for a, _ in pairs) / n) * (sum(b == k for _, b in pairs) / n) for k in cats)
    return (po - pe) / (1 - pe), po, n


CH2 = coded("checklist", (RATER, SECOND)); V2 = coded("verdict", (RATER, SECOND))
both = [v for v in CH2.values() if len(v) == 2]
k, po, n = kappa([(bool(v[RATER].get(c)), bool(v[SECOND].get(c))) for v in both for c in crit])
put("kappa_chk", round(k, 2)); put("agree_chk", round(100 * po)); put("kappa_chk_n", n)
k, po, n = kappa([(bool(v[RATER].get("FDR")), bool(v[SECOND].get("FDR"))) for v in both])
put("kappa_fdr", round(k, 2))
k, po, n = kappa([(bool(v[RATER].get("donor_aware")), bool(v[SECOND].get("donor_aware"))) for v in both])
put("kappa_donor", round(k, 2))
bv = [v for v in V2.values() if len(v) == 2]
k, po, n = kappa([(v[RATER].get("reports_difference"), v[SECOND].get("reports_difference")) for v in bv])
put("kappa_difference", round(k, 2)); put("kappa_verdict_n", n)
k, po, n = kappa([(v[RATER].get("acidification"), v[SECOND].get("acidification")) for v in bv])
put("kappa_acid", round(k, 2))

# ---------------------------------------------------------------- write
# Supplementary Table 1: every run of this study, with its coded conclusion and the genes it rests on
REFS = {"run0": "real", "opus_cs3_original": "real", **{r["label"]: f"shuffle{r['seed']}" for r in runs},
        **{lab: f"planted{int(lab.split('_s')[1].rstrip('b'))}" for lab in plant_runs["all"]}}
with open(OUT / "supplementary_table_1_runs.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["run", "model", "data", "reports_difference", "acidification", "summary_quote", "main_genes",
                "best_ttest_fdr_main_genes", "best_deseq2_padj_main_genes"])
    for lab, ref in REFS.items():
        if lab not in V:
            continue
        t = {x["gene"]: x for x in csv.DictReader(open(REF / f"de_{ref}.csv"))}
        d = {x[""]: x for x in csv.DictReader(open(REF / f"deseq2_{ref}.csv"))}
        genes = sorted({str(g).strip().upper() for a in V[lab].values() for g in a.get("main_genes") or []})
        tq = [float(t[g]["fdr_bh"]) for g in genes if g in t]
        dq = [float(d[g]["padj"]) for g in genes if g in d and d[g]["padj"]]
        first = V[lab][sorted(V[lab])[0]]
        w.writerow([lab, "Opus 4.8" if lab.startswith("opus") else "GLM 5.2", ref, agreed(lab, "reports_difference"),
                    agreed(lab, "acidification"), first.get("quote", ""), " ".join(genes),
                    f"{min(tq):.3g}" if tq else "", f"{min(dq):.3g}" if dq else ""])

if disagreements:
    print("WARNING: coders disagree on", disagreements)
(OUT / "numbers.json").write_text(json.dumps({"numbers": N, "runs": runs, "lead_genes": lead_rows, "checklist": chk,
                                              "disagreements": disagreements}, indent=1, default=float))


def tex_name(k):
    parts = k.replace("-", "_").split("_")
    out = "".join(p[:1].upper() + p[1:] for p in parts)
    digits = {"0": "Zero", "1": "One", "2": "Two", "3": "Three", "4": "Four", "5": "Five", "6": "Six", "7": "Seven", "8": "Eight", "9": "Nine"}
    return "".join(digits.get(ch, ch) for ch in out)


def tex_val(k, v):
    if isinstance(v, str):
        return v
    if isinstance(v, (int, np.integer)):
        return fmt_int(v)
    if "padj" in k or "_tq" in k or "_tp" in k or k.endswith("_p") or "minq" in k or "min_t" in k or "min_d" in k:
        return f"{v:.2g}" if v >= 0.001 else f"{v:.1e}".replace("e-0", "\\times10^{-").replace("e-", "\\times10^{-") + ("}" if "e" in f"{v:.1e}" else "")
    return f"{v:.2f}"


with open(OUT / "numbers.tex", "w") as fh:
    fh.write("% generated by make_numbers.py; do not edit\n")
    for k, v in N.items():
        fh.write(f"\\newcommand{{\\n{tex_name(k)}}}{{{tex_val(k, v)}}}\n")
print(json.dumps(N, indent=0, default=float)[:3000])
