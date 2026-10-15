# SIGMETRICS 2027 submission

The reproduction paper (`docs/paper/paper.md`) typeset for ACM SIGMETRICS 2027,
which publishes in POMACS.

- **Deadline:** Winter cycle. Abstract registration 4 January 2027, paper 11 January 2027, both 23:59 AoE. Submit at https://sigmetrics27winter.hotcrp.com.
- **Format:** `\documentclass[acmsmall,screen,review]{acmart}` as the call prescribes, plus `anonymous` for double anonymous review. Up to 20 pages of technical content, references unlimited. Margins, spacing and font sizes may not be changed.
- **Class version:** `acmart.cls` here is v2.20 (2026/08/16), generated from the CTAN source. The local copy takes precedence over whatever the TeX installation carries.

## Build

```bash
python3 make_figures.py                  # figures/*.pdf, from the paper's own tables
tectonic -X compile main.tex             # main.pdf, the anonymous submission
tectonic -X compile preview-authors.tex  # preview-authors.pdf, names shown
```

`main.pdf` is what you upload. `preview-authors.pdf` shows the camera-ready
author block and has no line numbers; it is gitignored and must never be
submitted, because the review is double anonymous.

The red numbers in the margin of `main.pdf` come from the `review` option the
call prescribes. Reviewers cite them; they disappear in the camera-ready.

On Overleaf, upload this folder as is and compile with XeLaTeX or pdfLaTeX.

## Before submitting

- [ ] Choose the track on HotCRP. Measurement & Applied Modeling fits best.
- [ ] Declare conflicts with PC members.
- [ ] Fill in the reproducibility declaration: what is released (code, configurations, result files) and where. The call prefers Zenodo over personal sites.
- [ ] Confirm the generative-AI paragraph in Section 2 states the actual extent of use. The call requires that disclosure in the Methods section.
- [ ] Confirm the artifact sentence in Appendix B matches what you will release.
- [ ] Check that the PDF names no author: `pdftotext main.pdf - | grep -i -E 'sharma|saini|behl|vellore'` should print nothing.
- [ ] Agree the author order and confirm Dr. Suganya R and Mr. S. Vijayaragavan agree to be named as authors.
- [ ] Add every author on HotCRP (it needs names and emails even though the PDF is anonymous).
- [ ] For the camera-ready version: remove `anonymous` and `review`, add each author's email, and check whether Mr. Vijayaragavan's affiliation should also name VIT, where he is Professor of Practice.
