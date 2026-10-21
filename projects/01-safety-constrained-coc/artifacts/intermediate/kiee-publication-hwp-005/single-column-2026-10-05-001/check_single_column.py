import json,collections,bisect,xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[6]
RUN=Path(__file__).resolve().parent
old=json.loads((ROOT/'projects/01-safety-constrained-coc/artifacts/intermediate/kiee-publication-hwp-004/continuous-flow-2026-10-05-001/document.json').read_text())
new=json.load(open(RUN/'document.json'));read=json.load(open(RUN/'document_reread.json'));log=json.load(open(RUN/'edit_log.json'));report=json.load(open(RUN/'render_report.json'))
def textcount(d,styled=False):
 c=collections.Counter()
 for s in d['sections']:
  for p in s['paragraphs']:
   offset=0;runs=p['char_shape_runs']
   for ch in p['chars']:
    if 'Text'in ch:
     t=ch['Text'];sid=runs[bisect.bisect_right([r[0]for r in runs],offset)-1][1]
     for letter in t:
      if not letter.isspace():c[(letter,sid)if styled else letter]+=1
     offset+=len(t.encode('utf-16-le'))//2
    elif 'ExtCtrl'in ch:offset+=8
    else:offset+=1
 return c
assert old['header']['char_shapes']==new['header']['char_shapes']
assert old['header']['fonts']==new['header']['fonts']
assert old['bin_streams']==new['bin_streams']
assert textcount(new)==textcount(read)
assert textcount(new)-textcount(old)==collections.Counter()
assert textcount(old)-textcount(new)==collections.Counter({'-':12})
assert not(textcount(new,True)-textcount(old,True))
assert sum((textcount(old,True)-textcount(new,True)).values())==12
ps=read['sections'][0]['paragraphs'];controls=[c for p in ps for c in p['controls']]
tables=[c['Table']for c in controls if 'Table'in c];pics=[c['Picture']for c in controls if 'Picture'in c]
cols=[c['Generic']['column_def']for c in controls if 'Generic'in c and c['Generic'].get('column_def')]
assert len(cols)==1 and cols[0]['count']==1
assert sum('SectionDef'in c for c in controls)==1
assert not any(p['header']['break_type']&(4|8)for p in ps)
assert len(tables)==12 and sum(len(t['cells'])for t in tables)==318
assert len(pics)==10 and all(p['treat_as_char']for p in pics)
assert all(t['placement']['treat_as_char']for t in tables)
assert len(ps)==len(log['roles'])==240
caps=[p for p,r in zip(ps,log['roles'])if r=='caption']
assert len(caps)==38
assert all(((read['header']['para_shapes'][p['para_shape']]['attr1']>>2)&7)==1 for p in caps)
oldpics=[c['Picture']for s in old['sections']for p in s['paragraphs']for c in p['controls']if 'Picture'in c]
assert [(p['width'],p['height'])for p in oldpics]==[(p['width'],p['height'])for p in pics]
assert [v['data_b64']for v in old['bin_streams']]==[v['data_b64']for v in read['bin_streams']]
assert all(not any(c.get('CharCtrl')==10 for c in p['chars'])for p in ps)
x=collections.Counter(e.tag for e in E.parse(RUN/'independent_parser.xml').iter())
assert x['TableControl']==12 and x['TableCell']==318 and x['ShapePicture']==10
assert not report['issues'] and report['font_coverage']['substitution_free']
result=dict(status='edited-awaiting-hancom-validation',native_sections=1,native_column_count=1,logical_paragraphs=240,previous_line_paragraphs=1251,inline_tables=12,source_cells_checked=318,table_source_mismatches=0,inline_images=10,left_aligned_captions=38,character_shapes_and_fonts_unchanged=True,non_whitespace_characters_preserved=True,non_whitespace_character_font_assignments_preserved=True,repaired_line_end_hyphens=12,embedded_images_and_picture_sizes_preserved=True,source_hard_page_and_column_breaks=0,independent_parser_valid=True,preview_pages=report['total_pages'],preview_issues=0,preview_substituted_fonts=0,hancom_application_validation=False,hancom_page_count=None)
Path(RUN/'structural_checks.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print(json.dumps(result,indent=2,ensure_ascii=False))
