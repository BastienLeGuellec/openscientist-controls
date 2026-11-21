"""DESeq2-style reference analysis for case study 3 (PyDESeq2, a reimplementation of R's DESeq2).

Same pseudobulk as reference_de.py: for each of the 8 donors, raw counts summed over its AT8+ (tangle-bearing)
and over its MAP2+ (tangle-free) neurons. Model: counts ~ donor + condition (negative binomial), so each donor
is compared with itself; Wald test for AT8 vs MAP2; Benjamini-Hochberg adjusted p-values (DESeq2's padj, with
its independent filtering). Genes with fewer than 10 counts in 8 or more samples are dropped beforehand.

Usage: .venv-de/bin/python deseq2_de.py <out_dir> <label>=<file.h5ad> [...]
"""
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).parent))
from reference_de import KEY_GENES, SETS, col  # noqa: E402

from pydeseq2.dds import DeseqDataSet  # noqa: E402
from pydeseq2.default_inference import DefaultInference  # noqa: E402
from pydeseq2.ds import DeseqStats  # noqa: E402


def pseudobulk(path):
    f = h5py.File(path, "r")
    raw = f["raw"]["X"]
    X = sparse.csr_matrix((raw["data"][:], raw["indices"][:], raw["indptr"][:]), shape=tuple(raw.attrs["shape"]))
    var = f["raw"]["var"] if "feature_name" in f["raw"]["var"] else f["var"]
    genes = col(var, "feature_name")
    label, donor = col(f["obs"], "SORT"), col(f["obs"], "donor_id")
    samples = [(d, s) for d in sorted(set(donor)) for s in ("AT8", "MAP2")]
    ind = sparse.csr_matrix(np.array([(donor == d) & (label == s) for d, s in samples], dtype=np.float32))
    counts = np.asarray((ind @ X).todense()).round().astype(int)
    names = [f"d{d}_{s}" for d, s in samples]
    df = pd.DataFrame(counts, index=names, columns=genes)
    df = df.T.groupby(level=0).sum().T                      # merge duplicated gene symbols
    meta = pd.DataFrame({"donor": [f"d{d}" for d, _ in samples], "condition": [s for _, s in samples]}, index=names)
    keep = (df >= 10).sum(0) >= 8
    return df.loc[:, keep], meta


def run(path):
    counts, meta = pseudobulk(path)
    inf = DefaultInference(n_cpus=2)
    dds = DeseqDataSet(counts=counts, metadata=meta, design="~donor + condition", refit_cooks=True,
                       inference=inf, quiet=True)
    dds.deseq2()
    st = DeseqStats(dds, contrast=["condition", "AT8", "MAP2"], inference=inf, quiet=True)
    st.summary()
    return st.results_df


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    for arg in sys.argv[2:]:
        label, path = arg.split("=", 1)
        r = run(path)
        r.to_csv(out / f"deseq2_{label}.csv")
        padj = r["padj"].fillna(1.0)
        print(f"\n== {label}: {len(r)} genes tested; padj<0.05: {(padj < 0.05).sum()}; padj<0.10: {(padj < 0.10).sum()}; "
              f"nominal p<0.05: {(r['pvalue'] < 0.05).sum()}")
        top = r.assign(padj=padj).sort_values("padj").head(6)
        print("   top genes:", ", ".join(f"{g} ({row.log2FoldChange:+.2f}, padj={row.padj:.2g})" for g, row in top.iterrows()))
        for sname, rule in SETS.items():
            m = [g for g in r.index if rule(g)]
            if m:
                sub = r.loc[m]
                up = int(((sub.padj.fillna(1) < 0.05) & (sub.log2FoldChange > 0)).sum())
                dn = int(((sub.padj.fillna(1) < 0.05) & (sub.log2FoldChange < 0)).sum())
                print(f"   set {sname:42s} n={len(m):2d} mean log2FC {sub.log2FoldChange.mean():+.3f}  padj<0.05: {up} up, {dn} down")
        for g in KEY_GENES:
            if g in r.index:
                row = r.loc[g]
                print(f"   {g:9s} log2FC {row.log2FoldChange:+.3f}  p={row.pvalue:.3g}  padj={row.padj:.3g}")


if __name__ == "__main__":
    main()
