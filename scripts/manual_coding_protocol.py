"""Protocol for the manual coding of the OpenScientist reports (manual_coding/protocol.docx).

Usage: python -I scripts/manual_coding_protocol.py, then scripts/manual_coding_prepare.py copies it into the packets.
The item definitions are those given to the language-model coder (scripts/audit_reports.py) and, for the five
criteria, the wording of Extended Data Table 2 of Roberts et al.; the decision rules for borderline cases are added
for the human coders.
"""
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

MA = Path(__file__).resolve().parents[1]
OUT = MA / "manual_coding/protocol.docx"

d = Document()
s = d.sections[0]
s.page_width, s.page_height = Cm(21.0), Cm(29.7)
s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Cm(2.2)
for name, size, bold in (("Normal", 10.5, False), ("Title", 17, True), ("Heading 1", 12.5, True),
                         ("List Bullet", 10.5, False), ("List Number", 10.5, False)):
    st = d.styles[name]
    st.font.name, st.font.size, st.font.bold = "Arial", Pt(size), bold
    st.font.color.rgb = RGBColor(0, 0, 0)
    rpr = st.element.get_or_add_rPr()
    f = rpr.find(qn("w:rFonts"))
    if f is None:
        f = OxmlElement("w:rFonts"); rpr.append(f)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        f.set(qn(a), "Arial")
    for a in list(f.attrib):
        if a.lower().endswith("theme"):
            del f.attrib[a]
    st.paragraph_format.space_after = Pt(5)
    st.paragraph_format.space_before = Pt(12 if name == "Heading 1" else 0)
    st.paragraph_format.line_spacing = 1.12


def p(text, style=None, bold_lead=None):
    par = d.add_paragraph(style=style)
    if bold_lead:
        par.add_run(bold_lead).bold = True
    par.add_run(text)
    return par


d.add_paragraph("Manual coding of OpenScientist reports: protocol", style="Title")
p("Controls for case study 3 of Roberts et al., Nature Medicine 2026 (OpenScientist). Coders: B.L.G., S.H.K., K.B.")

d.add_heading("Why we code by hand", 1)
p("Our analysis rests on how each OpenScientist report reads: whether it presents a difference between "
  "tangle-bearing and tangle-free neurons, what it concludes about lysosomal acidification, and whether it meets the "
  "five criteria the paper uses to judge reports (its Extended Data Table 2). So far a language model has coded the "
  "reports, and a second model agreed with it well on the conclusions but less well on the criteria (Cohen's κ 0.61 "
  "for multiple-testing correction). Two human codings of each report will give a reference, measure how far the "
  "models can be trusted, and decide which model, if any, codes the remaining reports.")

d.add_heading("What you receive", 1)
for t in ("index.html: the list of your reports, in the order to code them.",
          "reports/Rxx.html: the reports, each with a random identifier only. Open them in a browser. Figures are "
          "omitted, the text is complete.",
          "coding_sheet_<your initials>.xlsx: one row per report on the 'Coding' sheet, and a short 'Gene claims' "
          "sheet. Every answer cell has a drop-down list.",
          "This protocol."):
    p(t, "List Bullet")
p("With three coders, each report is coded by two of you, and each of you codes 40 reports. Plan on about 8 minutes "
  "per report and 20 seconds per gene claim, about 6 hours in total, which can be split over several sittings.")

d.add_heading("Blinding", 1)
p("The 60 reports come from OpenScientist runs on the original data, on copies with the tangle labels shuffled, and "
  "on copies with a planted effect, by two language models, in random order. Code what each report says, not whether "
  "you think it is right, and do not try to work out where it came from. Do not open manual_coding/key.csv in the "
  "repository, and do not discuss reports with the other coders until both of you have returned your sheets.")

d.add_heading("What OpenScientist was asked", 1)
p("“This is a single soma transcriptomic dataset of tangle-bearing and tangle-free neurons. Compare healthy to "
  "diseased neurons to investigate how is the proteostasis network rewired with the appearance of tau pathology. "
  "Investigate in particular if lysosomal acidification is changing.” The data are excitatory neurons from 8 donors "
  "with Alzheimer's disease, each neuron sorted as AT8+ (tangle-bearing) or MAP2+ (tangle-free).")

d.add_heading("How to code a report", 1)
p("Read the summary and the conclusions first: they decide items 1 and 2. Then look through the methods and results "
  "for items 3 to 7. When an item is borderline, choose the closer answer and write a short quote or note in "
  "'Evidence or doubts'.")

d.add_heading("The items", 1)
items = [
    ("1. Reports a difference (yes / no). ",
     "Yes if the report presents, as a finding of its own analysis, any difference in gene expression between "
     "tangle-bearing (AT8+) and tangle-free (MAP2+) neurons, in the proteostasis network or elsewhere, including "
     "modest, compensatory or selective changes. No only if it concludes that the two groups do not differ, or that no "
     "difference survives its own tests. A report that finds acidification unchanged but presents another "
     "tangle-related change as a finding is coded yes."),
    ("2. Acidification conclusion. ",
     "The report's conclusion on lysosomal acidification in tangle-bearing neurons, as its summary or conclusions state "
     "it. Impaired: reduced, impaired, failing, or dysregulated towards less acidification. Compensated: changing in a "
     "way the report reads as compensation, defence or support of acidification. Altered otherwise: changing, without a "
     "clear direction. Unchanged: no change at the transcript level. Not addressed: the report does not conclude on "
     "acidification. If the report gives both a defect and a compensation, code the one its summary leads with."),
    ("3. C1 (yes / no). ", "Compares AT8 (tangle-bearing) against MAP2 (tangle-free) neurons."),
    ("4. C2 (yes / no). ", "Characterises how the proteostasis network is rewired, naming at least two arms (for "
     "example autophagy, the ubiquitin-proteasome system, chaperones, the unfolded protein response, the lysosome)."),
    ("5. C3 (yes / no). ", "Addresses lysosomal acidification specifically."),
    ("6. FDR, multiple-testing correction (yes / no). ",
     "False discovery rate corrected for multiple testing. Yes if the report states that the findings it presents are "
     "corrected for multiple testing (false discovery rate, Benjamini–Hochberg, Bonferroni, q values), even if only "
     "within the gene sets or modules it tested. No if its findings rest on uncorrected P values only, or if it does "
     "not say."),
    ("7. Donor-aware (yes / no). ",
     "Treats the 8 donors as the sample size rather than the 22,492 cells, by pairing or pseudobulk. A model with donor "
     "as a random effect also counts. No if the statistics behind its findings treat neurons as independent "
     "observations."),
]
for lead, text in items:
    p(text, bold_lead=lead)

d.add_heading("Gene claims sheet", 1)
p("Each row is a gene claim that the language model extracted from one of your reports, with the quote it gave. Check "
  "it against the report and choose: yes (the report states that this gene is higher or lower in AT8+ than in MAP2+ "
  "neurons as a finding of its own analysis, in the direction given), wrong direction, not a finding (mentioned only "
  "as background, as a hypothesis, or in another comparison such as across donors or subtypes), or not found.")

d.add_heading("Returning your sheet and what happens next", 1)
for t in ("Save the coding sheet under its original name and send it to B.L.G.",
          "Once both coders of a report have returned their sheets, the disagreements are listed in an adjudication "
          "sheet. The two coders resolve each one by discussion, still without the key.",
          "Only then is the key opened. We report agreement between coders (Fleiss' κ), agreement of each language "
          "model with the human consensus (Cohen's κ), and the main results recomputed with the human coding."):
    p(t, "List Number")

OUT.parent.mkdir(exist_ok=True)
d.save(OUT)
print("written", OUT)
