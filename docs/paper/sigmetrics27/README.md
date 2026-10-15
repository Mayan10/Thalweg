# SIGMETRICS 2027 submission

The reproduction paper (`docs/paper/paper.md`) typeset for ACM SIGMETRICS 2027,
which publishes in POMACS.

- **Deadline:** Winter cycle. Abstract registration 4 January 2027, paper 11 January 2027, both 23:59 AoE. Submit at https://sigmetrics27winter.hotcrp.com.
- **Format:** `\documentclass[acmsmall,screen,review]{acmart}` as the call prescribes, plus `anonymous` for double anonymous review. Up to 20 pages of technical content, references unlimited. Margins, spacing and font sizes may not be changed.
- **Class version:** `acmart.cls` here is v2.20 (2026/08/16), generated from the CTAN source. The local copy takes precedence over whatever the TeX installation carries.

## Build

```bash
python3 make_figures.py          # figures/*.pdf, from the paper's own tables
tectonic -X compile main.tex     # main.pdf
```

On Overleaf, upload this folder as is and compile with XeLaTeX or pdfLaTeX.

## Before submitting

- [ ] Choose the track on HotCRP. Measurement & Applied Modeling fits best.
- [ ] Declare conflicts with PC members.
- [ ] Fill in the reproducibility declaration: what is released (code, configurations, result files) and where. The call prefers Zenodo over personal sites.
- [ ] Confirm the generative-AI paragraph in Section 2 states the actual extent of use. The call requires that disclosure in the Methods section.
- [ ] Confirm the artifact sentence in Appendix B matches what you will release.
- [ ] Check that the PDF names no author: `pdftotext main.pdf - | grep -i -E 'sharma|saini|behl|vellore'` should print nothing.
- [ ] For the camera-ready version, remove `anonymous` and `review` from the class options.
