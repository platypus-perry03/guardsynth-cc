import json,sys
j=json.load(open(sys.argv[1]));bad=[]
if len(j['sections'])!=1:bad.append(f"page-sized sections: {len(j['sections'])}")
for si,s in enumerate(j['sections']):
 for pi,p in enumerate(s['paragraphs']):
  if p['header']['break_type']&8:bad.append(f'forced source-column break at {si}:{pi}')
  for c in p['controls']:
   if ('Table'in c or 'Picture'in c):
    size=j['header']['char_shapes'][p['char_shape_runs'][0][1]]['base_size']
    if size<600:bad.append(f'object anchor font {size} at {si}:{pi}')
    for seg in p['line_segs']:
     if seg['text_height']!=seg['line_height']:bad.append(f'object line has inconsistent text height at {si}:{pi}')
print(json.dumps({'problems':bad},indent=2));assert not bad
