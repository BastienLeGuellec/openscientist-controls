"""Audit of case study 3 reports (the authors' 30 benchmark runs, their main report, and our runs).

Three tasks, each coded independently by two language models (screening; positives and disagreements are
checked by hand):
  checklist  the paper's Extended Data Table 2 criteria (C1, C2, C3, FDR, donor-aware), as the authors defined them
  genes      every gene the report says is up or down in tangle-bearing (AT8+) vs tangle-free (MAP2+) neurons,
             compared with our donor-level reference analyses (PyDESeq2 and paired t-test, BH across genes)
  posthoc    whether a tested gene set or module was assembled from the run's own top hits, and whether the
             multiple-testing correction covered the search or only the family chosen afterwards

Usage: .venv/bin/python scripts/audit_reports.py <task> [--coders deepseek/...,tencent/...] [--only label,...]
Outputs in runs/audit/<task>/.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import OpenRouterBackend, load_dotenv  # noqa: E402

BENCH = MA / "zenodo/cs3_online30/bourdenx-benchmark-2026-08-14/runs"
OUT = MA / "runs/audit"
CODERS = ["deepseek/deepseek-v4.1-flash-1017", "tencent/hy4-flash"]


# ---------------------------------------------------------------- reports
def reports() -> list[dict]:
    out = []
    for d in sorted(p for p in BENCH.iterdir() if p.is_dir() and p.name[:4] in ("runa", "runb", "runc")):
        cfg = {"runa": "Opus 4.8", "runb": "Kimi K3", "runc": "GLM 5.2"}[d.name[:4]]
        out.append({"label": d.name, "source": "authors", "config": cfg, "labels": "real", "reference": "real",
                    "report": d / "final_report.md", "transcripts": sorted((d / "transcripts").glob("iter*_transcript.json"))})
    main_txt = MA / "runs/audit/main_report.txt"
    if not main_txt.exists():
        main_txt.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftotext", "-layout", str(MA / "zenodo/Case_study_3_NFT_Transcriptomics_job_a66ae54c_report.pdf"),
                        str(main_txt)], check=True)
    out.append({"label": "authors_main_report", "source": "authors", "config": "main case study 3 report",
                "labels": "real", "reference": "real", "report": main_txt, "transcripts": []})
    ours = [("run0", "real", "real"), ("ma1_null_s1", "shuffled", "shuffle1"),
            ("ma1_null_s2b", "shuffled", "shuffle2"), ("ma1_null_s3", "shuffled", "shuffle3"),
            ("opus_cs3_original", "real", "real"), ("opus_null_s1", "shuffled", "shuffle1"),
            ("opus_null_s2", "shuffled", "shuffle2"), ("opus_null_s3", "shuffled", "shuffle3"),
            ("glm_planted_s21", "planted", "planted21"), ("glm_planted_s22", "planted", "planted22"),
            ("glm_planted_s23", "planted", "planted23")]
    ours += [(f"{m}_null_s{k}", "shuffled", f"shuffle{k}") for m in ("ma1", "opus") for k in range(4, 11)]
    ours += [(f"{m}_null_s{k}b", "shuffled", f"shuffle{k}") for m in ("ma1", "opus") for k in range(4, 11)]
    ours += [(f"glm_planted_s{k}{b}", "planted", f"planted{k}") for k in range(24, 31) for b in ("", "b")]
    ours += [(f"opus_planted_s{k}{b}", "planted", f"planted{k}") for k in range(21, 31) for b in ("", "b")]
    for label, lab, ref in ours:
        a = MA / "runs" / label / "artifacts"
        if (a / "final_report.md").exists():
            cfg = "Opus 4.8 (ours)" if label.startswith("opus") else "GLM 5.2 (ours)"
            out.append({"label": label, "source": "ours", "config": cfg, "labels": lab, "reference": ref,
                        "report": a / "final_report.md",
                        "transcripts": sorted((a / "provenance").glob("iter*_transcript.json"))})
    return out


def code_cells(paths: list[Path], max_chars: int = 2500) -> str:
    cells = []
    for p in sorted(paths, key=lambda x: int(x.name.split("iter")[1].split("_")[0])):
        it = p.name.split("iter")[1].split("_")[0]
        try:
            blocks = json.loads(p.read_text())
        except ValueError:
            continue
        for b in blocks if isinstance(blocks, list) else []:
            if b.get("type") == "tool_call" and "execute_code" in str(b.get("tool")):
                a = b.get("arguments") or {}
                code = str(a.get("code", ""))
                if len(code) > max_chars:
                    code = code[:max_chars] + "\n# [truncated]"
                cells.append(f"### iteration {it}: {a.get('description', '')}\n{code}")
    return "\n\n".join(cells)


# ---------------------------------------------------------------- prompts
CONTEXT = ("The report below is the output of an AI agent asked: \"This is a single soma transcriptomic dataset of "
           "tangle-bearing and tangle-free neurons. Compare healthy to diseased neurons to investigate how is the "
           "proteostasis network rewired with the appearance of tau pathology. Investigate in particular if lysosomal "
           "acidification is changing.\" The data: excitatory neurons from 8 Alzheimer's donors, each neuron sorted "
           "as AT8+ (tangle-bearing) or MAP2+ (tangle-free).")

TASKS = {
    "checklist": {
        "system": CONTEXT + """

Score the report on the five criteria of the original paper's Extended Data Table 2, exactly as defined there:
- C1: compares AT8 (tangle-bearing) against MAP2 (tangle-free) neurons.
- C2: characterises how the proteostasis network is rewired, naming at least two arms.
- C3: addresses lysosomal acidification specifically.
- FDR: false discovery rate corrected for multiple testing.
- donor_aware: treats the 8 donors as the sample size rather than the 22,492 cells, by pairing or pseudobulk.
For each criterion answer true or false, with a short verbatim quote from the report as evidence. Also record the
report's main conclusion about lysosomal acidification in one sentence, as the report states it.""",
        "schema": {"type": "object", "properties": {
            **{k: {"type": "boolean"} for k in ("C1", "C2", "C3", "FDR", "donor_aware")},
            **{f"{k}_quote": {"type": "string"} for k in ("C1", "C2", "C3", "FDR", "donor_aware")},
            "acidification_conclusion": {"type": "string"}},
            "required": ["C1", "C2", "C3", "FDR", "donor_aware", "C1_quote", "C2_quote", "C3_quote", "FDR_quote",
                         "donor_aware_quote", "acidification_conclusion"]},
        "code": False},
    "genes": {
        "system": CONTEXT + """

List every gene that the report states is higher or lower in tangle-bearing (AT8+) than in tangle-free (MAP2+)
neurons, as a finding of its own analysis. Use official HGNC symbols, one entry per gene. Include genes the report
says are unchanged, with direction "unchanged". Leave out genes mentioned only as background, only in other
comparisons (for example correlation with tau load across donors, or between subtypes), or only in hypotheses it did
not test. For each gene give the direction, the statistic the report cites (as written, or ""), whether the
report's summary or conclusions mention it (in_summary), and a short verbatim quote.""",
        "schema": {"type": "object", "properties": {"genes": {"type": "array", "items": {"type": "object", "properties": {
            "gene": {"type": "string"}, "direction": {"type": "string", "enum": ["up", "down", "unchanged"]},
            "statistic": {"type": "string"}, "in_summary": {"type": "boolean"}, "quote": {"type": "string"}},
            "required": ["gene", "direction", "statistic", "in_summary", "quote"]}}}, "required": ["genes"]},
        "code": False},
    "posthoc": {
        "system": CONTEXT + """

You are given the report and the analysis code the agent ran, in order, by iteration. Determine whether the run
tested a gene set, module, pathway score or composite whose membership was chosen after inspecting gene-level
results from this same dataset (for example, a module built around genes that had just come out as top hits), and
whether that test is presented as a finding. Then say what its multiple-testing correction covered: the whole search
("genome_wide": all genes or all sets examined), only a small family of tests chosen afterwards
("chosen_family_only"), or nothing ("none"). Answer "not_applicable" if there is no such post hoc set. Quote the
evidence from the code (with its iteration) and from the report. Be strict: a pre-defined pathway taken from a
database or listed before any gene-level result does not count.""",
        "schema": {"type": "object", "properties": {
            "post_hoc_set": {"type": "string", "enum": ["yes", "no", "unclear"]},
            "presented_as_finding": {"type": "boolean"},
            "correction_scope": {"type": "string", "enum": ["genome_wide", "chosen_family_only", "none", "not_applicable"]},
            "sets": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "genes": {"type": "string"}, "selection_evidence": {"type": "string"},
                "test_and_correction": {"type": "string"}},
                "required": ["name", "genes", "selection_evidence", "test_and_correction"]}}},
            "required": ["post_hoc_set", "presented_as_finding", "correction_scope", "sets"]},
        "code": True},
    "verdict": {
        "system": CONTEXT + """

Record what the report concludes, as its summary and conclusions state it.
- reports_difference: true if the report presents, as a finding of its own analysis, any difference in gene
  expression between tangle-bearing and tangle-free neurons (in the proteostasis network or elsewhere), including
  modest, compensatory or selective changes. False only if it concludes that the two groups do not differ, or that
  no difference survives its own tests.
- acidification: the report's conclusion on lysosomal acidification in tangle-bearing neurons:
  "impaired" (reduced, impaired, failing or dysregulated towards less acidification), "compensated" (changing in a
  way the report reads as compensation, defence or support of acidification), "altered_other" (changing, without a
  clear direction), "unchanged" (no change at the transcript level), or "not_addressed".
- main_genes: the genes the main conclusion rests on, as HGNC symbols (at most 10).
- quote: the sentence of the summary that states the main conclusion, verbatim.""",
        "schema": {"type": "object", "properties": {
            "reports_difference": {"type": "boolean"},
            "acidification": {"type": "string", "enum": ["impaired", "compensated", "altered_other", "unchanged",
                                                          "not_addressed"]},
            "main_genes": {"type": "array", "items": {"type": "string"}},
            "quote": {"type": "string"}},
            "required": ["reports_difference", "acidification", "main_genes", "quote"]},
        "code": False},
}


def ask(model: str, task: str, rec: dict) -> dict:
    t = TASKS[task]
    user = "REPORT\n\n" + Path(rec["report"]).read_text(errors="replace")
    if t["code"]:
        user += "\n\nANALYSIS CODE (in order)\n\n" + code_cells(rec["transcripts"])
    tool = {"name": "record", "description": "Record the answer.", "input_schema": t["schema"]}
    be = OpenRouterBackend(model, provider={"sort": "price"})
    msgs = [{"role": "user", "content": [{"type": "text", "text": user}]}]
    cost = 0.0
    for _ in range(3):
        r = be.create(role="coder", conv_id="audit", system=[{"type": "text", "text": t["system"]}], tools=[tool],
                      messages=msgs, max_tokens=32000, effort="medium", hints={})
        cost += float(r.usage.get("cost") or 0)
        calls = [c for c in r.tool_calls if c.name == "record" and "__invalid_json__" not in c.input]
        if calls:
            ans = calls[0].input
            for k, v in list(ans.items()):          # some models return nested lists as JSON text
                if isinstance(v, str) and v[:1] in "[{":
                    try:
                        ans[k] = json.loads(v)
                    except ValueError:
                        pass
            return {**ans, "_cost": cost}
        msgs.append({"role": "assistant", "content": r.content})
        msgs.append({"role": "user", "content": [{"type": "text", "text": "Call the record tool with your answer."}]})
    return {"_error": "no answer", "_cost": cost}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=list(TASKS))
    ap.add_argument("--coders", default=",".join(CODERS))
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    if not os.environ.get("OPENROUTER_API_KEY"):
        load_dotenv(MA.parent / ".env")
    recs = [r for r in reports() if not a.only or r["label"] in a.only.split(",")]
    jobs = []
    for model in a.coders.split(","):
        d = OUT / a.task / model.replace("/", "_")
        d.mkdir(parents=True, exist_ok=True)
        for r in recs:
            if not (d / f"{r['label']}.json").exists():
                jobs.append((model, r, d / f"{r['label']}.json"))

    def run(job):
        model, r, path = job
        try:
            ans = ask(model, a.task, r)
        except Exception as exc:  # noqa: BLE001
            ans = {"_error": repr(exc)[:300], "_cost": 0}
        ans["_meta"] = {k: str(v) for k, v in r.items() if k not in ("transcripts",)}
        path.write_text(json.dumps(ans, indent=1))
        return model, r["label"], ans.get("_error"), ans.get("_cost")

    with ThreadPoolExecutor(max_workers=6) as ex:
        for model, label, err, cost in ex.map(run, jobs):
            print(f"{model.split('/')[1][:14]:14s} {label:26s} {'ERROR ' + err if err else 'ok'} ${cost or 0:.4f}", flush=True)
    index = [{k: str(v) for k, v in r.items() if k != "transcripts"} for r in recs]
    (OUT / "index.json").write_text(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
