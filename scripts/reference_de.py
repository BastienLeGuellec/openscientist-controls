"""Reference analysis for case study 3: donor-level pseudobulk, paired test, Benjamini-Hochberg across genes.

For each donor, raw counts are summed over its AT8+ (tangle-bearing) and over its MAP2+ (tangle-free) neurons,
giving 8 donor pairs. Genes with at least 10 counts per million in at least 8 of the 16 pseudobulk samples are
kept. Each gene gets a paired t-test on log2 CPM (AT8 minus MAP2, n = 8 donors), and p-values are adjusted by
Benjamini-Hochberg across all kept genes. A gene-set score (mean of the genes' within-donor log2 fold changes)
is tested the same way for the gene families of the paper's mechanism.

Usage: python3 -I reference_de.py <out_dir> <label>=<file.h5ad> [...]
"""
import csv
import sys
from pathlib import Path

import h5py
import numpy as np
from scipy import sparse, stats

SETS = {
    "V-ATPase V1": lambda g: g.startswith("ATP6V1"),
    "V-ATPase V0": lambda g: g.startswith("ATP6V0"),
    "V-ATPase accessory": lambda g: g in ("ATP6AP1", "ATP6AP2"),
    "H+ leak channels (TPC, MCOLN, TMEM175)": lambda g: g in ("TPCN1", "TPCN2", "MCOLN1", "MCOLN2", "MCOLN3", "TMEM175"),
    "Cl- counter-ion (CLCN7, OSTM1)": lambda g: g in ("CLCN7", "OSTM1"),
}
KEY_GENES = ["ATP6V1A", "ATP6V1B2", "ATP6V1H", "ATP6V0A1", "ATP6V0D1", "ATP6AP2", "TMEM175", "MCOLN1", "TPCN1",
             "TPCN2", "CLCN7", "TFEB", "TFE3", "PSEN1", "CTSS", "CTSZ", "VAMP7", "RAB2A"]


def col(group, key):
    g = group[key]
    if isinstance(g, h5py.Group) and "categories" in g:
        return g["categories"][:].astype(str)[g["codes"][:]]
    return g[:].astype(str)


def bh(p):
    p = np.asarray(p, float)
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(q)
    out[order] = np.minimum(q, 1)
    return out


def analyse(path):
    f = h5py.File(path, "r")
    raw = f["raw"]["X"]
    X = sparse.csr_matrix((raw["data"][:], raw["indices"][:], raw["indptr"][:]),
                          shape=tuple(raw.attrs["shape"]))
    var = f["raw"]["var"] if "feature_name" in f["raw"]["var"] else f["var"]
    genes = col(var, "feature_name")
    label, donor = col(f["obs"], "SORT"), col(f["obs"], "donor_id")
    donors = sorted(set(donor))
    samples = [(d, s) for d in donors for s in ("AT8", "MAP2")]
    ind = sparse.csr_matrix(np.array([(donor == d) & (label == s) for d, s in samples], dtype=np.float32))
    pb = np.asarray((ind @ X).todense())                       # 16 x genes, summed raw counts
    cpm = pb / pb.sum(1, keepdims=True) * 1e6
    keep = (cpm >= 10).sum(0) >= 8
    lc = np.log2(cpm[:, keep] + 1)
    g = genes[keep]
    diff = lc[0::2] - lc[1::2]                                  # AT8 minus MAP2, one row per donor
    t, p = stats.ttest_1samp(diff, 0.0, axis=0)
    q = bh(p)
    res = {"n_genes": int(keep.sum()), "n_fdr05": int((q < 0.05).sum()), "n_fdr10": int((q < 0.10).sum()),
           "n_p05": int((p < 0.05).sum()), "genes": {}, "sets": {}}
    for i, name in enumerate(g):
        if name in KEY_GENES:
            res["genes"][name] = (float(diff[:, i].mean()), float(p[i]), float(q[i]), int((np.sign(diff[:, i]) == np.sign(diff[:, i].mean())).sum()))
    for sname, rule in SETS.items():
        m = np.array([rule(x) for x in g])
        if m.sum():
            score = diff[:, m].mean(1)
            ts, ps = stats.ttest_1samp(score, 0.0)
            res["sets"][sname] = (int(m.sum()), float(score.mean()), float(ps))
    top = np.argsort(q)[:10]
    res["top"] = [(g[i], float(diff[:, i].mean()), float(q[i])) for i in top]
    return res, (g, diff.mean(0), p, q)


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for arg in sys.argv[2:]:
        label, path = arg.split("=", 1)
        res, (g, lfc, p, q) = analyse(path)
        summary[label] = res
        with open(out / f"de_{label}.csv", "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(["gene", "log2fc_AT8_vs_MAP2", "p", "fdr_bh"])
            for row in zip(g, lfc, p, q):
                w.writerow([row[0], f"{row[1]:.6g}", f"{row[2]:.6g}", f"{row[3]:.6g}"])
        print(f"\n== {label}: {res['n_genes']} genes kept; FDR<0.05: {res['n_fdr05']}; FDR<0.10: {res['n_fdr10']}; "
              f"nominal p<0.05: {res['n_p05']} (expected by chance ~{round(0.05 * res['n_genes'])})")
        print("   top genes by FDR:", ", ".join(f"{a} ({b:+.2f}, q={c:.2g})" for a, b, c in res["top"][:6]))
        for s, (n, m, ps) in res["sets"].items():
            print(f"   set {s:42s} n={n:2d} mean log2FC {m:+.3f}  p={ps:.3g}")
        for k in KEY_GENES:
            if k in res["genes"]:
                m, pp, qq, agree = res["genes"][k]
                print(f"   {k:9s} log2FC {m:+.3f}  p={pp:.3g}  FDR={qq:.3g}  same sign in {agree}/8 donors")


if __name__ == "__main__":
    main()
