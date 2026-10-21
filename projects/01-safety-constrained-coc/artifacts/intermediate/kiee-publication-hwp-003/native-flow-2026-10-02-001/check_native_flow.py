import json,sys
j=json.load(open(sys.argv[1]));issues=[];tables=[];pictures=[];columns=[]
def walk(ps,depth=0):
 for p in ps:
  for c in p['controls']:
   if 'Generic' in c and c['Generic'].get('column_def'):columns.append(c['Generic']['column_def'])
   if 'Table' in c:
    t=c['Table'];tables.append((depth,t))
    if depth:issues.append('nested table')
    h=t.get('placement',{}).get('height',0)
    if not p['line_segs'] or max(s['line_height']for s in p['line_segs'])<h:issues.append(f'table anchor cache does not reserve {h}')
    for cell in t['cells']:walk(cell['paragraphs'],depth+1)
   if 'Picture' in c:
    pic=c['Picture'];pictures.append(pic)
    h=pic['height']
    if not p['line_segs'] or max(s['line_height']for s in p['line_segs'])<h:issues.append(f'picture anchor cache does not reserve {h}')
for s in j['sections']:walk(s['paragraphs'])
if len(tables)!=12:issues.append(f'table count {len(tables)} != 12')
if not any(c['count']==2 for c in columns):issues.append('no native two-column definition')
print(json.dumps({'issues':issues,'tables':len(tables),'pictures':len(pictures),'native_column_definitions':len(columns)},indent=2))
assert not issues
