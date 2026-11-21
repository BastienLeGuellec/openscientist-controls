"""Figures and Source Data of the case study 3 controls, from numbers.json (make_numbers.py), the coded
reports in runs/audit (one rater, RATER below, as in make_numbers.py) and the reference analyses in runs/reference_de.
Journal style at final size (183 mm): two type sizes (7 pt labels, 6 pt annotations), 8 pt bold panel letters, bold
only for panel letters and key labels, no titles inside panels, vector PDF with editable text.
Colour always means the data condition (blue real labels, orange shuffled labels, green planted effect); marker shape
means the model; fill means the outcome.

Figure 1
  a, design.  b, outcome of each run.  c, the paper's five criteria (its Extended Data Table 2), matched by model,
  real-label runs against shuffled-label runs, all coded by the same rater.  d, gene claims per report against the
  share supported by the standard analysis.
Extended Data Fig. 1
  a, genes with FDR < 0.05 in each data copy (broken axis).  b, paired t-test P-value distributions.
Source Data: source_data_fig1.xlsx and source_data_extended_data_fig1.xlsx, one sheet per panel.

Run with a Python that has matplotlib, pandas and openpyxl (e.g. anaconda).
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
MA = HERE.parent
REF = MA / "runs/reference_de"
J = json.loads((HERE / "numbers.json").read_text())
N, RUNS = J["numbers"], J["runs"]
RATER = "tencent_hy4-flash"                   # as in make_numbers.py

REAL, SHUF, PLANT = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2 = "#000000", "#3d3d3d"
L, S = 7, 6                                   # label and annotation sizes (pt)
MARK = {"GLM 5.2": "o", "Claude Opus 4.8": "s", "Kimi K3": "^"}
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Liberation Sans", "Arial", "Helvetica"],
                     "font.size": S, "axes.labelsize": L, "xtick.labelsize": S, "ytick.labelsize": S,
                     "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                     "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
                     "xtick.minor.width": 0.4, "xtick.major.size": 2, "ytick.major.size": 2, "xtick.minor.size": 1.2,
                     "legend.fontsize": S, "pdf.fonttype": 42, "svg.fonttype": "none"})
mm = 1 / 25.4


def spines(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def letter(fig, x, y, s):
    fig.text(x, y, s, fontsize=8, fontweight="bold", color=INK, va="top", ha="left")


def load(task):
    out = {}
    for f in (MA / "runs/audit" / task / RATER).glob("*.json"):
        a = json.loads(f.read_text())
        if "_error" not in a:
            out[f.stem] = a
    return out


V, CHK = load("verdict"), load("checklist")
by_seed = {(r["model"], r["seed"]): r["label"] for r in RUNS}
planted_labels = sorted(lab for lab in V if lab.startswith("glm_planted"))
MODEL_OF_CONFIG = {"Opus 4.8": "Claude Opus 4.8", "Kimi K3": "Kimi K3", "GLM 5.2": "GLM 5.2"}
authors_real = {lab: MODEL_OF_CONFIG[a["_meta"]["config"]] for lab, a in CHK.items()
                if a["_meta"].get("source") == "authors" and a["_meta"].get("config") in MODEL_OF_CONFIG}
assert len(authors_real) == 30, len(authors_real)

claims = defaultdict(lambda: [0, 0])                                  # label -> [claims, supported], rater only
for g in csv.DictReader(open(MA / "runs/audit/gene_claims_scored.csv")):
    if g["direction"] != "unchanged" and g["coder"] == RATER:
        claims[g["label"]][0] += 1
        claims[g["label"]][1] += g["verdict"] == "supported"

# ================================================================== Figure 1
W, H = 180, 156                                   # Extended Data page width is 180 mm
fig = plt.figure(figsize=(W * mm, H * mm))
src = {}

# ---------------------------------------------------------------- a, design
A_H = 33
ax = fig.add_axes([0, 1 - (A_H + 1) / H, 1, A_H / H])
ax.set_xlim(0, W)
ax.set_ylim(0, A_H)
ax.axis("off")
real_pat = [[1, 1, 1, 0, 0, 0], [1, 1, 1, 0, 0, 0]]
shuf_pat = [[1, 0, 0, 1, 1, 0], [0, 1, 1, 0, 0, 1]]


def donor(x0, y0, pattern, edge, plus=False):
    ax.add_patch(FancyBboxPatch((x0, y0), 10.5, 13.5, boxstyle="round,pad=0,rounding_size=1.0", facecolor="white",
                                edgecolor=edge, linewidth=0.7))
    for i, lab in enumerate(pattern):
        cx, cy = x0 + 3.2 + 4.2 * (i // 3), y0 + 10.6 - 3.8 * (i % 3)
        ax.add_patch(Circle((cx, cy), 1.0, facecolor=INK if lab else "white", edgecolor=INK, linewidth=0.5))
        if plus and lab:
            ax.text(cx + 1.75, cy + 0.15, "+", color=PLANT, fontsize=S, fontweight="bold", ha="center", va="center")


cond = [(4, REAL, "Real labels", "as sorted in the study", real_pat, False),
        (44, SHUF, "Shuffled labels", "permuted within each donor", shuf_pat, False),
        (84, PLANT, "Planted effect", "shuffled, then 4 genes raised\n1.5-fold in labelled AT8+", shuf_pat, True)]
for x0, col, title, sub, pat, plus in cond:
    ax.text(x0, 32.2, title, fontsize=L, color=INK, va="top", fontweight="bold")
    ax.text(x0, 29.2, sub, fontsize=S, color=INK2, va="top", linespacing=1.1)
    donor(x0, 10.5, pat[0], col, plus)
    donor(x0 + 13, 10.5, pat[1], col, plus)
    ax.text(x0 + 26.5, 17.2, "…", fontsize=L, color=INK2, ha="center", va="center")
    ax.text(x0 + 5.25, 9.4, "donor 1", fontsize=S, color=INK2, ha="center", va="top")
    ax.text(x0 + 18.25, 9.4, "donor 2", fontsize=S, color=INK2, ha="center", va="top")
    ax.plot([x0 + 14.5, x0 + 14.5], [4.6, 6.2], color=INK, linewidth=0.6)
ax.plot([18.5, 120], [4.6, 4.6], color=INK, linewidth=0.6)
ax.plot([120, 120], [4.6, 24.5], color=INK, linewidth=0.6)
ax.add_patch(Circle((5, 1.4), 0.9, facecolor=INK, edgecolor=INK, linewidth=0.5))
ax.text(6.8, 1.4, "labelled tangle-bearing (AT8+)", fontsize=S, va="center")
ax.add_patch(Circle((44, 1.4), 0.9, facecolor="white", edgecolor=INK, linewidth=0.5))
ax.text(45.8, 1.4, "labelled tangle-free (MAP2+)", fontsize=S, va="center")
for yc, head, body in ((24.5, "OpenScientist", "case study 3 prompt and settings,\nGLM 5.2 or Claude Opus 4.8"),
                       (10.5, "Standard per-donor analysis", "DESeq2 and paired t-test,\ncorrected for all genes tested")):
    ax.add_patch(FancyArrowPatch((120, yc), (125.5, yc), arrowstyle="-|>", mutation_scale=5, color=INK, linewidth=0.6))
    ax.add_patch(FancyBboxPatch((125.8, yc - 5.6), 53.5, 11.2, boxstyle="round,pad=0,rounding_size=1.0",
                                facecolor="white", edgecolor=INK, linewidth=0.5))
    ax.text(127.6, yc + 4.0, head, fontsize=L, fontweight="bold", va="top")
    ax.text(127.6, yc + 0.5, body, fontsize=S, color=INK2, va="top", linespacing=1.2)
letter(fig, 0.004, 1 - 0.3 / H, "a")

# ---------------------------------------------------------------- b, outcome per run
B_TOP = A_H + 4
axb = fig.add_axes([0.125, 1 - (B_TOP + 43) / H, 0.39, 40 / H])
code = {"impaired": "I", "compensated": "C", "unchanged": "U", "altered_other": "A", "not_addressed": "N"}
rows_b = []
planted_by = {"glm": sorted(lab for lab in V if lab.startswith("glm_planted")),
              "opus": sorted(lab for lab in V if lab.startswith("opus_planted"))}


def cell(x, y, lab, col, data, model_name, copy):
    a = V[lab]
    diff = a.get("reports_difference") is True
    axb.add_patch(Rectangle((x + 0.07, y + 0.07), 0.86, 0.86, facecolor=col if diff else "white", edgecolor=col,
                            linewidth=0.8))
    axb.text(x + 0.5, y + 0.5, code.get(a.get("acidification"), "?"), ha="center", va="center", fontsize=S,
             color=INK, fontweight="bold")
    rows_b.append({"model": model_name, "data": data, "copy": copy, "run": lab, "reports_difference": diff,
                   "acidification": a.get("acidification")})


for yi, (m, name) in enumerate((("glm", "GLM 5.2"), ("opus", "Claude Opus 4.8"))):
    for k in range(1, 11):                                              # shuffled-label copies 1-10
        cell(k - 1, 1 - yi, by_seed[(m, k)], SHUF, "shuffled labels", name, k)
    for q, lab in enumerate(planted_by[m]):                             # planted-effect copies 21-30
        cell(q, -2.4 - yi, lab, PLANT, "planted effect", name, int(lab.split("_s")[1].rstrip("b")) - 20)
    if not planted_by[m]:
        axb.text(0.1, -2.4 - yi + 0.5, "not run", fontsize=S, va="center", color=INK2)
    for y0 in (1 - yi, -2.4 - yi):
        axb.text(-0.25, y0 + 0.5, name, ha="right", va="center", fontsize=L)
for k in range(1, 11):
    axb.text(k - 0.5, -0.05, str(k), ha="center", va="top", fontsize=S)
    axb.text(k - 0.5, -3.45, str(k), ha="center", va="top", fontsize=S)
axb.text(5, -0.5, "Shuffled-label copy", ha="center", va="top", fontsize=L)
axb.text(5, -3.9, "Planted-effect copy", ha="center", va="top", fontsize=L)
axb.set_xlim(-0.1, 10.2)
axb.set_ylim(-4.4, 2.0)
axb.axis("off")
fig.text(0.125, 1 - (B_TOP + 43.5) / H,
         "Filled: reports a tangle-related change    Open: reports no difference\nLetter: conclusion on lysosomal "
         "acidification (I impaired, C compensated,\nU unchanged, A altered otherwise)",
         fontsize=S, va="top", ha="left", linespacing=1.3)
letter(fig, 0.004, 1 - B_TOP / H, "b")
src["Fig1b"] = pd.DataFrame(rows_b)

# ---------------------------------------------------------------- c, the paper's criteria matched by model
D_W = 0.43 * W
axt = fig.add_axes([0.565, 1 - (B_TOP + 30) / H, 0.43, 28 / H])
axt.axis("off")
crit = [("C1", "C1, tangle-bearing vs tangle-free"),
        ("C2", "C2, two or more proteostasis arms"),
        ("C3", "C3, lysosomal acidification"),
        ("FDR", "Multiple-testing correction"),
        ("donor_aware", "Donors as the unit of analysis")]
published = {"Claude Opus 4.8": {"C1": 10, "C2": 10, "C3": 10, "FDR": 10, "donor_aware": 10},   # Extended Data Table 2
             "GLM 5.2": {"C1": 10, "C2": 10, "C3": 10, "FDR": 8, "donor_aware": 10}}
shuffled_of = {"Claude Opus 4.8": [by_seed[("opus", k)] for k in range(1, 11)],
               "GLM 5.2": [by_seed[("glm", k)] for k in range(1, 11)]}
real_of = {m: [lab for lab, mm_ in authors_real.items() if mm_ == m] for m in shuffled_of}
cols = [("Claude Opus 4.8", "real", REAL), ("Claude Opus 4.8", "shuffled", SHUF),
        ("GLM 5.2", "real", REAL), ("GLM 5.2", "shuffled", SHUF)]
axt.set_xlim(0, D_W)
axt.set_ylim(0, 28)
x_col = [42, 52, 63.5, 73.5]
for x0, x1, model in ((x_col[0], x_col[1], "Claude Opus 4.8"), (x_col[2], x_col[3], "GLM 5.2")):
    axt.text((x0 + x1) / 2, 27.8, model, ha="center", va="top", fontsize=L)
    axt.plot([x0 - 4, x1 + 4], [24.4, 24.4], color=INK, linewidth=0.4)
for j, (model, kind, col) in enumerate(cols):
    axt.add_patch(Rectangle((x_col[j] - 3.5, 22.3), 7.0, 0.8, facecolor=col, edgecolor="none"))
    axt.text(x_col[j], 21.8, kind, ha="center", va="top", fontsize=S)
rows_t = []
for i, (c, label) in enumerate(crit):
    y = 16.2 - i * 3.75
    axt.text(0.0, y, label, ha="left", va="center", fontsize=S)
    for j, (model, kind, col) in enumerate(cols):
        labs = real_of[model] if kind == "real" else shuffled_of[model]
        met, n = sum(bool(CHK[lab].get(c)) for lab in labs), len(labs)
        axt.text(x_col[j], y, f"{met}/{n}", ha="center", va="center", fontsize=S)
        row = {"criterion": label, "model": model, "labels": kind, "met (this study's coding)": met, "n": n}
        if kind == "real":
            row["met (published, Extended Data Table 2)"] = published[model][c]
        rows_t.append(row)
    if i < len(crit) - 1:
        axt.plot([0, D_W - 1], [y - 1.875, y - 1.875], color="#e6e6e6", linewidth=0.5)
letter(fig, 0.55, 1 - B_TOP / H, "c")
src["Fig1c"] = pd.DataFrame(rows_t)

# ---------------------------------------------------------------- d, claims made against claims supported
D_TOP = B_TOP + 56
axd = fig.add_axes([0.085, 0.085, 0.89, 1 - (D_TOP + 5) / H - 0.085])
rows_d = []
groups = ([("Real labels, authors' runs", lab, model, REAL, "white") for lab, model in authors_real.items()]
          + [("Real labels, this study", "run0", "GLM 5.2", REAL, INK),
             ("Real labels, this study", "opus_cs3_original", "Claude Opus 4.8", REAL, INK)]
          + [("Shuffled labels, this study", by_seed[(m, k)], name, SHUF, "white")
             for m, name in (("glm", "GLM 5.2"), ("opus", "Claude Opus 4.8")) for k in range(1, 11)]
          + [("Planted effect, this study", lab, "GLM 5.2" if lab.startswith("glm") else "Claude Opus 4.8", PLANT,
              "white") for lab in sorted(lab for lab in V if "_planted_s" in lab and lab in claims)])
rng = np.random.default_rng(1)
for grp, lab, model, col, edge in groups:
    n, s = claims[lab]
    if n == 0:
        continue
    pct = 100 * s / n
    y = pct if pct > 0 else -rng.uniform(0.5, 3.5)          # points at 0% are jittered below 0 so none is hidden
    axd.scatter(n, y, s=14, marker=MARK[model], facecolor=col, edgecolor=edge, linewidth=0.6 if edge == INK else 0.3,
                zorder=3, clip_on=False)
    rows_d.append({"labels": grp, "run": lab, "model": model, "directional gene claims": n, "supported": s,
                   "percent supported": round(pct, 1)})
axd.set_xscale("log")
axd.set_xlim(2, 300)
axd.set_xticks([3, 10, 30, 100, 300], ["3", "10", "30", "100", "300"])
axd.set_ylim(-5, 103)
axd.set_yticks([0, 25, 50, 75, 100])
axd.set_xlabel("Directional gene claims in the report")
axd.set_ylabel("Claims supported by the\nstandard analysis (%)")
spines(axd)
axd.text(3.6, 3.0, "all 20 shuffled-label reports at 0% (jittered below 0)", fontsize=S,
         va="bottom", ha="left", color=INK2)
h_lab = [Line2D([], [], ls="", marker="o", markersize=3.6, markerfacecolor=REAL, markeredgecolor="white",
                markeredgewidth=0.3, label="Real, authors' runs (Claude Opus 4.8, Kimi K3, GLM 5.2; n = 30)"),
         Line2D([], [], ls="", marker="o", markersize=3.6, markerfacecolor=REAL, markeredgecolor=INK,
                markeredgewidth=0.6, label="Real, this study (GLM 5.2, Claude Opus 4.8; n = 2)"),
         Line2D([], [], ls="", marker="o", markersize=3.6, markerfacecolor=SHUF, markeredgecolor="white",
                markeredgewidth=0.3, label="Shuffled, this study (n = 20)"),
         Line2D([], [], ls="", marker="o", markersize=3.6, markerfacecolor=PLANT, markeredgecolor="white",
                markeredgewidth=0.3,
                label=f"Planted effect, this study (n = {sum(1 for lab in V if '_planted_s' in lab and lab in claims)})")]
h_model = [Line2D([], [], ls="", marker=MARK[m], markersize=3.6, markerfacecolor="#9e9e9e", markeredgecolor="white",
                  markeredgewidth=0.3, label=m) for m in ("GLM 5.2", "Claude Opus 4.8", "Kimi K3")]
leg1 = axd.legend(handles=h_lab, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.98), handletextpad=0.3,
                  title="Labels", title_fontproperties={"weight": "bold", "size": S}, alignment="left",
                  borderaxespad=0.2, labelspacing=0.35)
axd.add_artist(leg1)
axd.legend(handles=h_model, frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.56), handletextpad=0.3,
           title="Model", title_fontproperties={"weight": "bold", "size": S}, alignment="left", borderaxespad=0.2,
           labelspacing=0.35)
letter(fig, 0.004, 1 - D_TOP / H, "d")
src["Fig1d"] = pd.DataFrame(rows_d)

fig.savefig(HERE / "extended_data_fig2.pdf")                 # the four-panel figure is Extended Data Fig. 2
fig.savefig(HERE / "extended_data_fig2.png", dpi=300)
plt.close(fig)
with pd.ExcelWriter(HERE / "source_data_extended_data_fig2.xlsx") as xw:
    for name in ("Fig1b", "Fig1c", "Fig1d"):
        src[name].to_excel(xw, sheet_name=name.replace("Fig1", "EDFig2"), index=False)

# ================================================================== Extended Data Fig. 1
fig = plt.figure(figsize=(180 * mm, 62 * mm))
src = {}
PLANTED_COPIES = [k for k in range(21, 31) if f"planted{k}_d_fdr05" in N]
copies = [("Real labels", ["real"], REAL), ("Shuffled labels\n(10 copies)", [f"shuffle{k}" for k in range(1, 11)], SHUF),
          (f"Planted effect\n({len(PLANTED_COPIES)} copies)", [f"planted{k}" for k in PLANTED_COPIES], PLANT)]
top = fig.add_axes([0.08, 0.62, 0.35, 0.3])
bot = fig.add_axes([0.08, 0.17, 0.35, 0.4])
rows_e = []
for i, (name, keys, col) in enumerate(copies):
    spread = 0.06 if len(keys) > 3 else 0.12
    for q, key in enumerate(keys):
        x = i + (q - (len(keys) - 1) / 2) * spread
        for pipe, filled in (("d", True), ("t", False)):
            v = N[f"{key}_{pipe}_fdr05"]
            ax_ = top if v > 100 else bot
            ax_.scatter(x + (0.02 if not filled else -0.02), v, s=8, facecolor=col if filled else "white",
                        edgecolor=col, linewidth=0.6, zorder=3)
            rows_e.append({"data copy": key, "method": "DESeq2" if pipe == "d" else "paired t-test",
                           "genes tested": N[f"{key}_{pipe}_genes"], "genes FDR < 0.05": v})
top.set_ylim(3000, 7000)
top.set_yticks([4000, 6000], ["4,000", "6,000"])
bot.set_ylim(-0.5, 7)
bot.set_yticks([0, 2, 4, 6])
for ax_ in (top, bot):
    ax_.set_xlim(-0.6, 2.6)
    spines(ax_)
top.spines["bottom"].set_visible(False)
top.set_xticks([])
bot.set_xticks(range(3), [c[0] for c in copies], fontsize=L)
bot.tick_params(axis="x", length=0)
d = 0.012
for yy in (0.62, 0.57):
    fig.add_artist(Line2D([0.08 - d, 0.08 + d], [yy - d, yy + d], color=INK, linewidth=0.5))
fig.text(0.015, 0.55, "Genes with FDR < 0.05", rotation=90, va="center", ha="center", fontsize=L)
top.text(0.12, N["real_d_fdr05"], f"{N['real_d_fdr05']:,} (DESeq2)", fontsize=S, va="center")
top.text(0.12, N["real_t_fdr05"], f"{N['real_t_fdr05']:,} (t-test)", fontsize=S, va="center")
bot.text(1, 1.0, "0 in 10 of 10 copies,\nboth methods", fontsize=S, ha="center", va="bottom")
bot.text(2, 5.6, f"DESeq2: {N['planted_rec_d']} of {N['planted_n_tests']} planted genes\n+ {N['planted_other_d']} other in total"
                 f"\nt-test: {N['planted_rec_t']} of {N['planted_n_tests']}", fontsize=S, ha="center", va="bottom")
bot.legend(handles=[Line2D([], [], ls="", marker="o", markersize=3.2, markerfacecolor=INK2, markeredgecolor=INK2,
                           label="DESeq2"),
                    Line2D([], [], ls="", marker="o", markersize=3.2, markerfacecolor="white", markeredgecolor=INK2,
                           label="Paired t-test")],
           frameon=False, loc="upper left", bbox_to_anchor=(0.0, 1.02), handletextpad=0.2)
letter(fig, 0.0, 0.99, "a")
src["EDFig1a"] = pd.DataFrame(rows_e)

axh = fig.add_axes([0.6, 0.17, 0.37, 0.75])
bins = np.linspace(0, 1, 21)
rows_h = []
for key, col, lw, lab in [(f"shuffle{k}", SHUF, 0.6, "Shuffled labels (10 copies)" if k == 1 else None)
                          for k in range(1, 11)] + [("real", REAL, 1.0, "Real labels")]:
    p = pd.read_csv(REF / f"de_{key}.csv")["p"].dropna().to_numpy()
    h, _ = np.histogram(p, bins=bins, density=True)
    counts, _ = np.histogram(p, bins=bins)
    axh.stairs(h, bins, color=col, linewidth=lw, label=lab, zorder=3 if key == "real" else 2)
    rows_h += [{"data copy": key, "bin from": round(bins[i], 2), "bin to": round(bins[i + 1], 2),
                "genes": int(counts[i]), "density": round(float(h[i]), 4)} for i in range(len(h))]
axh.axhline(1, color=INK2, linewidth=0.5, linestyle=(0, (2, 2)), zorder=1)
axh.set_xlim(0, 1)
axh.set_ylim(0, None)
axh.set_xlabel("Paired t-test P value (per gene)")
axh.set_ylabel("Density")
spines(axh)
axh.legend(frameon=False, loc="upper right", handlelength=1.2)
letter(fig, 0.52, 0.99, "b")
src["EDFig1b"] = pd.DataFrame(rows_h)
fig.savefig(HERE / "extended_data_fig1.pdf")
fig.savefig(HERE / "extended_data_fig1.png", dpi=300)
with pd.ExcelWriter(HERE / "source_data_extended_data_fig1.xlsx") as xw:
    for name, df in src.items():
        df.to_excel(xw, sheet_name=name, index=False)
print("written figure1, extended_data_fig1 and their Source Data files")

# ================================================================== Figure 1: what goes in changes, what comes out does not
# Columns are the data conditions, and colour means the condition everywhere (header frame and every output mark in
# that column). Marker shape gives the model, keyed once in the header; GLM 5.2 is always the upper line and Claude
# Opus 4.8 the lower. Real labels: the authors' benchmark runs of the two models we also ran on shuffled labels, coded
# by our rater. Planted runs are picked up as they are coded.
EMPTY = "#c8c8c8"
real_runs = {m: sorted(lab for lab, mm_ in authors_real.items() if mm_ == m) for m in ("GLM 5.2", "Claude Opus 4.8")}
shuf_runs = {"GLM 5.2": [by_seed[("glm", k)] for k in range(1, 11)],
             "Claude Opus 4.8": [by_seed[("opus", k)] for k in range(1, 11)]}
plant_runs = {"GLM 5.2": sorted(lab for lab in V if lab.startswith("glm_planted") and lab in CHK and lab in claims),
              "Claude Opus 4.8": sorted(lab for lab in V if lab.startswith("opus_planted") and lab in CHK
                                        and lab in claims)}
n_pg, n_po = len(plant_runs["GLM 5.2"]), len(plant_runs["Claude Opus 4.8"])
plant_sub = (f"this study, n = {n_pg} per model" if n_pg == n_po else
             f"this study, GLM 5.2 n = {n_pg}, Claude Opus 4.8 n = {n_po}" if n_po else f"this study, n = {n_pg}")
COLS = [("Real labels", "authors' runs, our coding, n = 10 per model", REAL, real_runs, "real"),
        ("Shuffled labels", "this study, n = 10 per model", SHUF, shuf_runs, "shuffled"),
        ("Planted effect", plant_sub, PLANT, plant_runs, "planted")]
MODELS = ("GLM 5.2", "Claude Opus 4.8")
YY = {"GLM 5.2": 1.25, "Claude Opus 4.8": 0.45}
PLANTED_GENES = {"TMEM175", "MCOLN1", "TPCN1", "TPCN2"}

# what the standard analysis finds in the planted copies the runs analysed
plant_copies = sorted({int(lab.split("_s")[1].rstrip("b")) for m in MODELS for lab in plant_runs[m]})
found, others = [], 0
for k in plant_copies:
    d = {r[""]: r for r in csv.DictReader(open(REF / f"deseq2_planted{k}.csv"))}
    sig = {g for g, r in d.items() if r["padj"] and float(r["padj"]) < 0.05}
    found.append(len(sig & PLANTED_GENES))
    others += len(sig - PLANTED_GENES)


def flagged(lab):                       # fails at least one of the five criteria of Extended Data Table 2
    return not all(bool(CHK[lab].get(c)) for c in ("C1", "C2", "C3", "FDR", "donor_aware"))


def mech(lab):
    return V[lab].get("reports_difference") is True


W1, H1 = 183, 104
fig = plt.figure(figsize=(W1 * mm, H1 * mm))
X0, CW, GAP = 40, 46, 2.5                # first column left edge, column width, gap (mm)
col_x = [X0 + i * (CW + GAP) for i in range(3)]


def box(x_mm, y_top_mm, w_mm, h_mm):     # axes placed in millimetres from the top-left corner
    return fig.add_axes([x_mm / W1, 1 - (y_top_mm + h_mm) / H1, w_mm / W1, h_mm / H1])


def row_title(y_top, title):
    fig.text(6 / W1, 1 - y_top / H1, title, fontsize=L, va="top", ha="left", linespacing=1.1)


rows_src = []
# ---------------------------------------------------------------- header: one donor box per condition, model key
hdr = box(0, 0, W1, 17)
hdr.set_xlim(0, W1)
hdr.set_ylim(0, 17)
hdr.axis("off")
pats = {"real": real_pat[0], "shuffled": shuf_pat[0], "planted": shuf_pat[0]}
for (title, sub, col, runs, kind), x in zip(COLS, col_x):
    hdr.text(x + CW / 2, 16.8, title, ha="center", va="top", fontsize=L, fontweight="bold")
    hdr.text(x + CW / 2, 13.6, sub, ha="center", va="top", fontsize=S, color=INK2)
    x0 = x + CW / 2 - 9
    hdr.add_patch(FancyBboxPatch((x0, 0.4), 9.5, 9.6, boxstyle="round,pad=0,rounding_size=1.0", facecolor="white",
                                 edgecolor=col, linewidth=0.7))
    for i, lab in enumerate(pats[kind]):
        cx, cy = x0 + 2.9 + 3.8 * (i // 3), 0.4 + 7.6 - 2.9 * (i % 3)
        hdr.add_patch(Circle((cx, cy), 0.85, facecolor=INK if lab else "white", edgecolor=INK, linewidth=0.5))
        if kind == "planted" and lab:
            hdr.text(cx + 1.55, cy + 0.15, "+", color=PLANT, fontsize=S, fontweight="bold", ha="center", va="center")
    hdr.text(x0 + 11, 7.6, "×8 donors", fontsize=S, va="center", color=INK2)
    if kind == "planted" and not n_po:
        hdr.text(x0 + 11, 2.6, "Claude Opus 4.8\nnot run", fontsize=S, va="center", color=INK2, linespacing=1.1)
hdr.text(6, 16.8, "Data given to OpenScientist", fontsize=L, va="top", fontweight="bold")
hdr.add_patch(Circle((7, 11.6), 0.85, facecolor=INK, edgecolor=INK, linewidth=0.5))
hdr.text(8.7, 11.6, "labelled tangle-bearing (AT8+)", fontsize=S, va="center")
hdr.add_patch(Circle((7, 8.6), 0.85, facecolor="white", edgecolor=INK, linewidth=0.5))
hdr.text(8.7, 8.6, "labelled tangle-free (MAP2+)", fontsize=S, va="center")
hdr.scatter([7], [4.4], marker=MARK["GLM 5.2"], s=12, color=INK2)
hdr.text(8.7, 4.4, "GLM 5.2 (upper line)", fontsize=S, va="center")
hdr.scatter([7], [1.6], marker=MARK["Claude Opus 4.8"], s=12, color=INK2)
hdr.text(8.7, 1.6, "Claude Opus 4.8 (lower line)", fontsize=S, va="center")

# ---------------------------------------------------------------- data band: genes the standard analysis finds
Y_DATA = 21
row_title(Y_DATA, "Genes that differ in the\nstandard analysis")
r1 = box(0, Y_DATA, W1, 7)
r1.set_xlim(0, W1)
r1.set_ylim(0, 7)
r1.axis("off")
pf = f"{min(found)} of 4" if min(found) == max(found) else f"{min(found)}–{max(found)} of 4"
pf_small = ("planted genes found in each copy" if min(found) == max(found) else
            f"planted genes found per copy\n(all 4 in {sum(f == 4 for f in found)} of {len(found)} copies)")
pf_small += f", plus {others} other gene{'s' if others != 1 else ''} in total"
vals = [(f"{N['real_d_fdr05']:,}", f"of {N['real_d_genes']:,} genes tested (DESeq2)"),
        ("0", f"in each of the {N['n_shuffles']} copies (DESeq2)"),
        (pf, pf_small.replace(", plus", "\nplus") if "\n" not in pf_small else pf_small.replace(", plus", ",\nplus"))]
for (big, small), x in zip(vals, col_x):
    r1.text(x + 2, 4.6, big, fontsize=L, fontweight="bold", va="center")
    r1.text(x + 2, 2.6, small, fontsize=S, va="top", color=INK2, linespacing=1.15)
    rows_src.append({"row": "genes differing (DESeq2, FDR < 0.05)", "column": "", "model": "", "run": "",
                     "value": big + " " + small.replace("\n", " ")})


def strip_row(y_top, h, title, value_of, xlim, xticks, xlabel, key, expected=None):
    row_title(y_top, title)
    for ci, ((ctitle, sub, col, runs, kind), x) in enumerate(zip(COLS, col_x)):
        ax_ = box(x + 2, y_top, CW - 4, h)
        if expected and kind in expected:
            ex = expected[kind]
            ax_.axvline(ex, color=INK, linewidth=0.6, linestyle=(0, (2, 1.5)), zorder=1)
            ax_.text(ex + 0.02 * (xlim[1] - xlim[0]), 2.05, f"expected {ex}", fontsize=S, va="top", ha="left")
        for m in MODELS:
            labs = runs[m]
            if not labs:
                continue
            yy = YY[m]
            vs = [value_of(lab) for lab in labs]
            jit = np.linspace(-0.12, 0.12, len(vs)) if len(vs) > 1 else [0]
            ax_.scatter(vs, [yy + j for j in jit], marker=MARK[m], s=10, facecolor=col, edgecolor="white",
                        linewidth=0.3, zorder=3, clip_on=False)
            if all(v == 0 for v in vs) and not (expected and kind in expected):
                ax_.text(xlim[0] + 0.05 * (xlim[1] - xlim[0]), yy, f"all {len(vs)} at 0", fontsize=S, color=INK2,
                         va="center")
            for lab, v in zip(labs, vs):
                rows_src.append({"row": key, "column": ctitle, "model": m, "run": lab, "value": round(v, 1)})
        ax_.set_xlim(*xlim)
        ax_.set_ylim(0, 2.05 if expected else 1.75)
        ax_.set_yticks([])
        ax_.set_xticks(xticks)
        for s_ in ("top", "right", "left"):
            ax_.spines[s_].set_visible(False)
        if ci == 1:
            ax_.set_xlabel(xlabel, fontsize=S, labelpad=1)


def unit_row(y_top, h, title, is_on, key):
    row_title(y_top, title)
    for (ctitle, sub, col, runs, kind), x in zip(COLS, col_x):
        ax_ = box(x + 2, y_top, CW - 4, h)
        ax_.set_xlim(0, 12.5)
        ax_.set_ylim(0, 1.75)
        ax_.axis("off")
        for m in MODELS:
            labs = runs[m]
            if not labs:
                continue
            yy = YY[m]
            k = 0
            for i, lab in enumerate(labs):
                on = is_on(lab)
                k += on
                ax_.add_patch(Rectangle((i + 0.1, yy - 0.3), 0.8, 0.6, facecolor=col if on else "white",
                                        edgecolor=col if on else EMPTY, linewidth=0.6))
                rows_src.append({"row": key, "column": ctitle, "model": m, "run": lab, "value": bool(on)})
            ax_.text(10.4, yy, f"{k}/{len(labs)}", fontsize=S, va="center", ha="left")


# ---------------------------------------------------------------- what OpenScientist reports
strip_row(35, 10, "Directional gene claims\nper report", lambda lab: claims[lab][0], (0, 140), [0, 50, 100],
          "claims per report", "directional gene claims per report", expected={"shuffled": 0, "planted": 4})
unit_row(55, 7.5, "Runs proposing a tangle-\nrelated mechanism", mech, "proposes a mechanism")
unit_row(65, 7.5, "Runs flagged by the\npaper's checklist", flagged, "fails at least one of the five criteria")
# ---------------------------------------------------------------- checked against the standard analysis
strip_row(82, 10, "Claims supported by the\nstandard analysis", lambda lab: 100 * claims[lab][1] / claims[lab][0],
          (0, 100), [0, 50, 100], "% of the report's claims", "percent of claims supported")
for y_top, h, txt in ((Y_DATA, 7, "data"), (35, 38, "what OpenScientist reports"), (82, 10, "checked")):
    fig.add_artist(Line2D([4 / W1] * 2, [1 - y_top / H1, 1 - (y_top + h) / H1], color=INK, linewidth=0.6))
    fig.text(2.4 / W1, 1 - (y_top + h / 2) / H1, txt, rotation=90, fontsize=S, va="center", ha="center",
             color=INK2)
fig.savefig(HERE / "figure1.pdf")
fig.savefig(HERE / "figure1.png", dpi=300)
plt.close(fig)
with pd.ExcelWriter(HERE / "source_data_fig1.xlsx") as xw:
    pd.DataFrame(rows_src).to_excel(xw, sheet_name="Fig1", index=False)
print("written figure1 (summary figure) and its Source Data")
