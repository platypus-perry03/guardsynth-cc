"""Build the author-approved English revision; preserve frozen evidence and Korean files."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path('REPOSITORY_ROOT')
OUT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001'
OLD = EVIDENCE / 'manuscript-revision-2026-09-30-001'
PAPER = OUT
assert '--update-current' in sys.argv or not (OUT / 'RESULT.json').exists(), 'Use --update-current only for an explicitly authorized in-place manuscript revision'
APPROVED_SOURCE = {'outside_sections_sha256': 'b4a8a5d362101124f7a88d88ee1ea3506d55a7c2a2296666e0f728211b44e463', 'main_tex_sha256': '66d747ee26dc41467bea3ca322b12a46048fcd97a38aa4c8e55a810f3d538660', 'methodology_sha256': 'cbee10a42ad611bd3dd0a0e2a120a1082df867c3b71cda6d477efeaeedd12302', 'experimental_md_sha256': '77a53dfd7578d5165c643b2b153f3f86ff397c054d726f0de6645af5dd130586', 'related_work_md_sha256': '1e49064716b7b332f30ada85078b8040ad11d1075350c58e710bee557b89dc5d', 'introduction_sha256': 'c97f2d6f79d66e9b83c0535997d83ec5b78f2dd1e59286b3da94fba19de101e9', 'outside_introduction_sha256': '4f3204ce516e1df8ebb81a9c98103160cd1f08a696059145c1e413f05459c167', 'outside_abstract_sha256': '30397100979a68daf9b6950f5ad4c20989a7154576e8d318b7327502d98fcee9', 'title_abstract_sha256': 'cf0410ead2a12cff8c921cb4be7db276e85cd855b88ef1fcdbfda9466f0602fa'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


source = (PAPER / 'main.tex').read_text()
abstract_prefix, abstract_body = source.split(r'\begin{abstract}', 1)
_, abstract_suffix = abstract_body.split(r'\end{abstract}', 1)
assert digest(abstract_prefix + r'\begin{abstract}' + r'\end{abstract}' + abstract_suffix) == APPROVED_SOURCE['outside_abstract_sha256'], 'Text outside the approved abstract revision changed'
assert sha(PAPER / 'IEEE_ACCESS_TITLE_ABSTRACT_V01_EN.md') == APPROVED_SOURCE['title_abstract_sha256']
intro_prefix, intro_body = source.split(r'\section{Introduction}', 1)
_, intro_suffix = intro_body.split(r'\section{Related Work}', 1)
assert digest(intro_prefix + r'\section{Related Work}' + intro_suffix) == APPROVED_SOURCE['outside_introduction_sha256'], 'Sections outside the approved introduction revision changed'
assert sha(PAPER / 'IEEE_ACCESS_INTRODUCTION_V01_EN.md') == APPROVED_SOURCE['introduction_sha256']
prefix, body = source.split(r'\section{Proposed Method}', 1)
_, body = body.split(r'\section{Experimental Setup}', 1)
_, suffix = body.split(r'\section{Results}', 1)
assert digest(prefix + r'\section{Results}' + suffix) == APPROVED_SOURCE['outside_sections_sha256'], 'Protected surrounding sections differ from the approved revision'
assert digest(source) == APPROVED_SOURCE['main_tex_sha256'], 'Integrated source differs from the approved revision'
assert sha(PAPER / 'IEEE_ACCESS_METHODOLOGY_V01_EN.md') == APPROVED_SOURCE['methodology_sha256']
assert sha(PAPER / 'IEEE_ACCESS_EXPERIMENTS_V01_EN.md') == APPROVED_SOURCE['experimental_md_sha256']
assert sha(PAPER / 'IEEE_ACCESS_RELATED_WORK_V01_EN.md') == APPROVED_SOURCE['related_work_md_sha256']
assert len(re.findall(r'\\caption\{', source)) == 25, 'Unexpected figure/table count'
assert 'temporal-boundary-en.pdf' not in source, 'Redundant boundary figure remains'
assert 'task-performance-en.pdf' not in source, 'Redundant performance figure remains'
assert not re.search(r'\\href\{\\detokenize\{[^}]+\}\}\{S[1-5]\}', source), 'Unexplained local code labels remain'
refs = set(re.findall(r'\\ref\{([^}]+)\}', source))
labels = re.findall(r'\\label\{([^}]+)\}', source)
assert len(labels) == len(set(labels)), 'Duplicate labels'
assert refs <= set(labels), f'Missing labels: {refs - set(labels)}'

protected = [p for p in OLD.rglob('*') if p.is_file()] + [p for p in PAPER.glob('*_KO.md') if 'REVISION_NOTES' not in p.name]
for run in ('temporal-experiment-closure-2026-09-29-001', 'multitask-contract-analysis-2026-09-30-001', 'expanded-diagnostics-analysis-2026-09-30-001', 'methodology-2026-09-30-001'):
    protected.extend((EVIDENCE / run).rglob('*.json'))
for evidence_root in (ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-external-methods-001/original-method-checks-2026-10-07-001', ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-reasoning-comparison-001/reasoning-comparison-2026-10-07-001'):
    protected.extend(p for p in evidence_root.rglob('*') if p.is_file())
for evidence_root in (ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-temporal-diversity-001', ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001/temporal-expansion-learning-2026-09-29-001', Path('projects/04-guardsynth-coc/artifacts/public/paper1-method-preservation-001/multitask-contract-analysis-2026-09-30-001')):
    protected.extend(p for p in evidence_root.rglob('*') if p.is_file() and p.suffix in ('.json', '.csv', '.md', '.pdf'))
position_hold_evidence = ROOT / 'projects/04-guardsynth-coc/artifacts/public/paper1-position-hold-training-001/position-hold-training-2026-10-08-001'
protected.extend(p for p in position_hold_evidence.rglob('*') if p.is_file() and p.suffix in ('.json', '.jsonl', '.csv', '.md', '.pdf', '.smt2'))
protected = list(dict.fromkeys(protected))
before = {str(p): sha(p) for p in protected}
tex = PAPER / 'main.tex'
job = 'ieee-access-manuscript-en'
steps = [
    ('build-en-1.log', ['/usr/bin/pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-jobname=' + job, tex.name]),
    ('build-bibtex.log', ['/usr/bin/bibtex', job]),
    ('build-en-2.log', ['/usr/bin/pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-jobname=' + job, tex.name]),
    ('build-en-3.log', ['/usr/bin/pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-jobname=' + job, tex.name]),
]
for log_name, command in steps:
    result = subprocess.run(command, cwd=OUT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (OUT / log_name).write_text(result.stdout)
    assert result.returncode == 0, result.stdout[-5000:]
bibliography_keys = re.findall(r'\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}', (OUT / (job + '.bbl')).read_text())
citation_keys = {key.strip() for group in re.findall(r'\\cite\{([^}]+)\}', source) for key in group.split(',')}
assert len(bibliography_keys) == len(set(bibliography_keys)), 'Duplicate bibliography entries'
assert citation_keys <= set(bibliography_keys), 'Missing bibliography entries'
log = (OUT / 'ieee-access-manuscript-en.log').read_text()
assert not re.search(r'LaTeX Warning:.*undefined|Missing character|multiply defined', log, re.I), 'Unresolved references, citations, or missing characters'
assert before == {str(p): sha(p) for p in protected}, 'Frozen snapshot, Korean sources, or experiment records changed'
page_count = int(re.search(r'Output written on .*?\((\d+) pages?', log)[1])
manifest = {
    'project_id': 'guardsynth-coc', 'run_id': OUT.name, 'parent_run': OLD.name,
    'scope': 'Author-approved English revisions R01-R42 and verified introduction and primary position-hold learning results of 2026-10-08',
    'update_mode': 'Explicitly authorized in-place revision',
    'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in (PAPER / 'main.tex', PAPER / 'IEEE_ACCESS_TITLE_ABSTRACT_V01_EN.md', PAPER / 'IEEE_ACCESS_INTRODUCTION_V01_EN.md', PAPER / 'IEEE_ACCESS_METHODOLOGY_V01_EN.md', PAPER / 'IEEE_ACCESS_EXPERIMENTS_V01_EN.md', PAPER / 'IEEE_ACCESS_DISCUSSION_V01_EN.md', PAPER / 'IEEE_ACCESS_CONCLUSION_V01_EN.md', PAPER / 'IEEE_ACCESS_RELATED_WORK_V01_EN.md', PAPER / 'references.bib', PAPER / 'template/IEEEtran.bst')},
    'approved_source': APPROVED_SOURCE,
    'protected_files_sha256': before,
    'captions_after': 25, 'figure_count': 9, 'table_count': 16,
    'revised_items': [f'R{n:02}' for n in range(1, 43)],
    'additional_revisions': ['Native external-method checks and task differences', 'External-comparison limitations and reasoning-control protocol', 'Supplementary reasoning-prompt results and archived comparison figure', 'Archived representation, wording/hard, image, and layer-specific error evaluations', 'Verified final introduction, cited recent studies, and supplementary sections S11-S12', 'Author-approved plain-English abstract replacement', 'Primary position-hold learning study with identical evaluation inputs, all before/after strata, and retained XY regression limitations', 'Replace the primary position-hold table with paired before/after accuracy and violation-rate plots; exact counts retained in S12', 'Explain real-scene video observations, external rules, applicability review, and EBLC input binding; distinguish the workflow from evaluated automatic extraction', 'Illustrate video and rule input paths, human confirmation, EBLC binding, and unresolved-candidate deferral', 'Remove automatic extraction from the research scope; clarify supplied-input selection, specification checks, and model evaluation'],
    'experiment_results_modified': False, 'korean_sources_and_pdfs_modified': False,
    'figures_regenerated': False, 'new_grounding_figure': {'file': 'figures/video-grounding-en.pdf', 'renderer': 'projects/04-guardsynth-coc/experiments/paper1_external_methods/build_video_grounding_manuscript_figure.py', 'renderer_sha256': sha(ROOT / 'projects/04-guardsynth-coc/experiments/paper1_external_methods/build_video_grounding_manuscript_figure.py'), 'figure_sha256': sha(OUT / 'figures/video-grounding-en.pdf'), 'scope': 'Supplied-input review and evidence binding; automated extraction outside scope'}, 'new_primary_figure': {'file': 'figures/position-hold-learning-en.pdf', 'source': 'frozen position-hold comparison_metrics.csv', 'renderer': 'projects/04-guardsynth-coc/experiments/paper1_external_methods/build_position_hold_manuscript_figure.py'}, 'new_figure_reformatted': 'reasoning-comparison-en.pdf uses the frozen comparison RESULT.json at manuscript width', 'pages': page_count,
    'bibliography': {'database': 'projects/04-guardsynth-coc/paper/ieee-access/references.bib', 'style': 'IEEEtran', 'entries': len(bibliography_keys), 'build_order': ['pdflatex', 'bibtex', 'pdflatex', 'pdflatex']},
}
(OUT / 'RUN_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
result_path = OUT / 'RESULT.json'
if result_path.exists():
    result = json.loads(result_path.read_text())
    result.update(pdf_sha256=sha(OUT / (job + '.pdf')), main_tex_sha256=sha(tex), pages_after=page_count)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'build': 'PASS', 'pages': page_count, 'references': 'RESOLVED', 'protected_files': len(before), 'frozen_evidence': 'UNCHANGED'}))
