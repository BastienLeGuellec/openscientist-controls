"""Arm N: permute the tangle label (obs.SORT, AT8/MAP2) among cells within each donor.

Writes a copy of the case study 3 .h5ad in which only two obs fields change:
- SORT: permuted within donor, so each donor keeps its numbers of AT8 and MAP2 cells;
- Sample.ID ("AD-AT8-1"): rewritten to match the new label, because it otherwise reveals the true one.
Everything else (counts, normalised matrix, barcodes, embeddings) is byte-identical.

Usage: python3 -I make_null.py <in.h5ad> <out.h5ad> <seed>
"""

import shutil
import sys

import h5py
import numpy as np


def categorical(group: h5py.Group) -> tuple[np.ndarray, np.ndarray]:
    return group["categories"][:].astype(str), group["codes"][:]


def main(src: str, dst: str, seed: int) -> None:
    shutil.copyfile(src, dst)
    rng = np.random.default_rng(seed)
    with h5py.File(dst, "r+") as f:
        obs = f["obs"]
        donor_cats, donor_codes = categorical(obs["donor_id"])
        sort_cats, sort_codes = categorical(obs["SORT"])
        sid_cats, sid_codes = categorical(obs["Sample.ID"])
        donors = donor_cats[donor_codes]
        old_sort = sort_cats[sort_codes]
        old_sid = sid_cats[sid_codes]

        new_codes = sort_codes.copy()
        for d in np.unique(donors):
            idx = np.flatnonzero(donors == d)
            new_codes[idx] = rng.permutation(sort_codes[idx])
        new_sort = sort_cats[new_codes]

        # Sample.ID is AD-<SORT>-<k>, with one k per donor: rebuild it from the new label.
        k_of = {}
        for d in np.unique(donors):
            ks = {s.rsplit("-", 1)[1] for s in old_sid[donors == d]}
            assert len(ks) == 1, (d, ks)
            k_of[d] = ks.pop()
        new_sid = np.array([f"AD-{s}-{k_of[d]}" for s, d in zip(new_sort, donors)])
        assert set(new_sid) <= set(sid_cats), "a rebuilt Sample.ID is not an existing category"
        lookup = {c: i for i, c in enumerate(sid_cats)}
        obs["SORT"]["codes"][...] = new_codes
        obs["Sample.ID"]["codes"][...] = np.array([lookup[s] for s in new_sid], dtype=sid_codes.dtype)

    # checks
    for d in np.unique(donors):
        m = donors == d
        assert (old_sort[m] == "AT8").sum() == (new_sort[m] == "AT8").sum()
    kept = (old_sort == new_sort).mean()
    print(f"seed {seed}: {len(new_sort)} cells, label unchanged for {kept:.1%} of cells "
          f"(chance level for these group sizes), counts per donor and label preserved")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
