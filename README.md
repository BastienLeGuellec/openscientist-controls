# OpenScientist case study 3: shuffled-label and planted-effect controls

Code to replicate a test of case study 3 of Roberts et al., "An open agentic AI co-scientist for clinical and
biomedical discovery", *Nature Medicine* (2026), doi:10.1038/s41591-026-04808-6.

OpenScientist is run with the authors' code, prompt and settings on their deposited case study 3 data, with the
tangle labels shuffled within each donor (no true difference) or with four lysosomal channel genes raised about
1.5-fold in one group (known effect), using GLM 5.2 and Claude Opus 4.8. Each report is compared with a standard
per-donor analysis of the same copy (pseudobulk DESeq2 and paired t-test, Benjamini-Hochberg correction) and coded on
the five criteria of the paper's Extended Data Table 2.

Bastien Le Guellec (Department of Neuroradiology, Lille University Hospital), Su Hwan Kim and Keno Bressem (Department
of Radiology, TUM Klinikum rechts der Isar, Technical University of Munich).

## Contents

| Folder | Contents |
|---|---|
| `scripts/` | data copies, OpenScientist job submission and collection, run queues, standard analysis, report coding, manual coding |
| `figures/` | `make_numbers.py` (every number, from the run outputs) and `make_figure.py` (figures and Source Data) |
| `os_bench_changes/` | how the OpenScientist build differs from upstream commit `e0dc8421`, and environment templates without keys |

## Replicating

1. Inputs: `scripts/fetch_inputs.sh` downloads the authors' Zenodo deposit (record 23988648, CC BY 4.0: the case
   study 3 data, the authors' 30 benchmark runs and the prompt) and checks the md5 sums.
2. Data copies, from `zenodo/cs3_main/job_a66ae54c/data/OteroGarcia_excitatory_subset.h5ad`:
   `python -I scripts/make_null.py <src.h5ad> data/null_seed<k>.h5ad <k>` for k = 1-10 (labels shuffled within each
   donor) and `python -I scripts/make_planted.py <src.h5ad> data/planted_seed<k>.h5ad <k>` for k = 21-30 (shuffled,
   then TMEM175, MCOLN1, TPCN1 and TPCN2 raised about 1.5-fold in neurons labelled AT8+).
3. OpenScientist: clone github.com/openscientist-io/openscientist, check out `e0dc8421`, apply
   `os_bench_changes/fixes_since_e0dc8421.diff` (the fixes listed in the authors' benchmark notes) and
   `os_bench_changes/local_changes.diff` (pinned agent tools, and the model proxy forwarding to the configured base
   URL so that Claude can be reached through OpenRouter). Copy an `env.*.example` to `.env`, fill in the keys and run
   `docker compose up -d`. Jobs are submitted with `scripts/os_submit_files.sh` (10 iterations, autonomous mode) and
   collected with `scripts/os_collect.sh` into `runs/<label>/`; `scripts/batch10_chain.sh` and
   `scripts/planted_chain.sh` are the queues used (one job at a time, with cost and disk guards).
4. Standard analysis of every copy: `scripts/reference_de.py` (paired t-test) and `scripts/deseq2_de.py` (PyDESeq2).
5. Report coding by two language models through OpenRouter (`OPENROUTER_API_KEY` in `../.env`):
   `scripts/audit_reports.py {checklist,genes,posthoc,verdict}`, then `scripts/audit_summary.py genes` and
   `scripts/barcode_check.py`.
6. Numbers and figures: in `figures/`, `python -I make_numbers.py`, then `python -I make_figure.py`.
7. Manual coding (blinded double coding of the 60 reports in the main figure): `scripts/manual_coding_protocol.py`,
   `scripts/manual_coding_prepare.py`, then `scripts/manual_coding_analyse.py` once the sheets are returned.

Python packages: anndata, h5py, numpy, pandas, scipy, pydeseq2, matplotlib, openpyxl, python-docx, markdown.

## License

The code is released under the MIT License (`LICENSE`).
