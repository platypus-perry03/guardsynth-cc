ROOT := $(abspath ../../../../..)
OUT := $(ROOT)/projects/01-safety-constrained-coc/artifacts/public/kiee-review-002/revision-2026-09-30-001
TEX_CACHE := $(OUT)/texlive-cache
LUALATEX := env TEXMFVAR=$(TEX_CACHE) lualatex -interaction=nonstopmode -halt-on-error -output-directory=$(OUT)
PUBLICATION_OUT := $(ROOT)/projects/01-safety-constrained-coc/artifacts/public/kiee-publication-001/publication-2026-10-01-001
PUBLICATION_LATEX := env TEXMFVAR=$(PUBLICATION_OUT)/texlive-cache lualatex -interaction=nonstopmode -halt-on-error -output-directory=$(PUBLICATION_OUT)

.PHONY: all manuscript rebuttal publication
all: manuscript rebuttal

manuscript:
	@mkdir -p $(OUT) $(TEX_CACHE)
	$(LUALATEX) main.tex
	cd $(OUT) && env BIBINPUTS=$(CURDIR): bibtex main
	$(LUALATEX) main.tex
	$(LUALATEX) main.tex
	cp $(OUT)/main.pdf main.pdf

rebuttal:
	@mkdir -p $(OUT) $(TEX_CACHE)
	$(LUALATEX) response-to-reviewer-1.tex
	$(LUALATEX) response-to-reviewer-1.tex
	cp $(OUT)/response-to-reviewer-1.pdf response-to-reviewer-1.pdf

publication:
	@mkdir -p $(PUBLICATION_OUT) $(PUBLICATION_OUT)/texlive-cache
	$(PUBLICATION_LATEX) publication.tex
	cd $(PUBLICATION_OUT) && env BIBINPUTS=$(CURDIR): bibtex publication
	$(PUBLICATION_LATEX) publication.tex
	$(PUBLICATION_LATEX) publication.tex
	cp $(PUBLICATION_OUT)/publication.pdf publication.pdf
