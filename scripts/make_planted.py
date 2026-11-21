"""Positive control: a within-donor shuffled copy (no real signal) with one planted effect that contradicts the
paper's mechanism: the proton-leak channels it reports as downregulated (TMEM175, MCOLN1, TPCN1, TPCN2) are raised
about 1.5-fold in the neurons labelled tangle-bearing (AT8) after the shuffle.

For each such neuron and gene with a nonzero raw count c, the new count is c + Poisson(c * (FOLD - 1)), so zeros stay
zero and the sparsity pattern is unchanged. The normalised matrix X (Seurat LogNormalize: log1p(count / nCount_RNA *
1e4)) is recomputed for the same entries. Everything else is as in make_null.py. The planted genes and fold are not
written into the file; they are printed and saved next to it as <out>.planted.json.

Usage: python3 -I make_planted.py <in.h5ad> <out.h5ad> <seed>
"""
import json
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from make_null import categorical, main as shuffle  # noqa: E402

GENES = ["TMEM175", "MCOLN1", "TPCN1", "TPCN2"]
FOLD = 1.5


def plant(path: str, seed: int) -> dict:
    rng = np.random.default_rng([seed, 777])
    with h5py.File(path, "r+") as f:
        obs = f["obs"]
        sort_cats, sort_codes = categorical(obs["SORT"])
        at8 = sort_cats[sort_codes] == "AT8"
        ncount = obs["nCount_RNA"][:]
        var = f["raw"]["var"] if "feature_name" in f["raw"]["var"] else f["var"]
        names = categorical(var["feature_name"])[0][categorical(var["feature_name"])[1]] \
            if isinstance(var["feature_name"], h5py.Group) else var["feature_name"][:].astype(str)
        cols = {g: int(np.flatnonzero(names == g)[0]) for g in GENES}
        raw, X = f["raw"]["X"], f["X"]
        indptr, indices = raw["indptr"][:], raw["indices"][:]
        assert np.array_equal(indptr, X["indptr"][:]) and np.array_equal(indices, X["indices"][:])
        rdata, xdata = raw["data"][:], X["data"][:]
        target = np.isin(indices, list(cols.values()))
        row_of = np.repeat(np.arange(len(indptr) - 1), np.diff(indptr))
        sel = np.flatnonzero(target & at8[row_of])
        before = rdata[sel].sum()
        rdata[sel] = rdata[sel] + rng.poisson(rdata[sel] * (FOLD - 1))
        xdata[sel] = np.log1p(rdata[sel] / ncount[row_of[sel]] * 1e4).astype(xdata.dtype)
        raw["data"][...] = rdata
        X["data"][...] = xdata
        info = {"genes": GENES, "fold": FOLD, "seed": seed, "entries_changed": int(len(sel)),
                "counts_before": float(before), "counts_after": float(rdata[sel].sum())}
    return info


if __name__ == "__main__":
    src, dst, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    shuffle(src, dst, seed)
    info = plant(dst, seed)
    Path(dst + ".planted.json").write_text(json.dumps(info, indent=1))
    print(info)
