"""Read-only review projection of a saved verification and its exact input snapshot."""
from copy import deepcopy
import json

from .common import digest

SOURCE_CODES={'CATALOG_MISSING','UNGROUNDED'}
CONTRADICTIONS={'ACTION_CONTRADICTION','RULE_CONTRADICTION','IDENTITY_CONFLICT','OBSERVATION_CONFLICT','RELATION_CONTRADICTION','POSTCONDITION_CONTRADICTION','PRECONDITION_CONTRADICTION','LIFECYCLE_CONFLICT','JUSTIFICATION_CONTRADICTION','CAN_ACTION_CONTRADICTION'}


def correction_review(baseline, current, snapshot, current_summary, stale):
    """Compare saved checks with current annotations; absence is not a proof of repair."""
    from .sequence import candidate
    if not baseline:
        return {'changed_inputs': [], 'issues': []}
    old={m['id']:m for m in baseline['inputs']['snapshot']['moments']}
    changed=[]
    for m in snapshot['moments']:
        prior=old.get(m['id'], {})
        for kind in ('sequence_coc', 'sequence_constraints'):
            before=prior.get('components', {}).get(kind, {}).get('payload', {})
            after=m.get('components', {}).get(kind, {}).get('payload', {})
            if candidate(before, kind)!=candidate(after, kind):
                changed.append({'moment_id':m['id'], 'ordinal':m['ordinal'], 'component':kind,
                                'before_revision':prior.get('revision'), 'revision':m.get('revision')})
    touched={x['moment_id'] for x in changed}
    prior_summary=summarize(baseline['inputs']['compiled'], baseline['result'], baseline['inputs']['snapshot'])
    latest={s['moment_id']:s for s in (current_summary or {}).get('scenes', [])}
    def locations(issue):
        return {(s.get('moment_id'), s.get('component'), json.dumps(s.get('path'))) for s in issue.get('sources', [])}
    issues=[]
    for scene in prior_summary['scenes']:
        for issue in scene['issues']:
            if scene['moment_id'] not in touched and not any(s.get('moment_id') in touched for s in issue.get('sources', [])):
                continue
            now=latest.get(scene['moment_id'], {})
            repeated=any(i['code']==issue['code'] and (bool(locations(i)&locations(issue)) or not locations(i) and not locations(issue)) for i in now.get('issues', []))
            status='PENDING' if stale else 'STILL_PRESENT' if repeated else 'NOT_EVALUATED' if now.get('input_status')!='READY' else 'NOT_REPORTED'
            issues.append({'moment_id':scene['moment_id'], 'ordinal':scene['ordinal'], 'issue_id':issue['issue_id'],
                           'code':issue['code'], 'title':issue.get('title') or issue.get('message') or issue['code'],
                           'property_ids':issue.get('property_ids', []), 'status':status})
    return {'baseline_job_id':baseline['id'], 'current_job_id':current['id'] if current else None,
            'verification_current':not stale, 'changed_inputs':changed, 'issues':issues}


def approved(moment,kind):
    c=moment.get('components',{}).get(kind);a=moment.get('approvals',{}).get(kind)
    return bool(c and not c.get('stale') and a and a.get('decision')=='APPROVE' and a.get('component_id')==c['id'] and a.get('dependency_digest')==digest(c.get('dependencies',{})))


def legacy_missing(d):
    valid=bool(d.get('evidence_refs') and d.get('evidence_note','').strip())
    if not valid or d.get('truth')=='CONFLICT':return True
    if d.get('scope_state')=='ENDED':return False
    return d.get('truth')=='UNKNOWN' or d.get('scope_state')=='UNKNOWN'


def unified_issues(issues, properties, inputs, models=None):
    """Link property findings to exact saved input, without altering solver output."""
    merged={};links={}
    def add(item,pid=None,status=None):
        item=deepcopy(item)
        sources=item.get('sources',[])
        # Source order and repeated source entries do not make a new finding.
        keys=sorted({json.dumps([s.get('moment_id'),s.get('component'),s.get('path'),s.get('value')],sort_keys=True,ensure_ascii=False) for s in sources})
        key=json.dumps([item['code'],keys,item.get('message') if not keys else None],ensure_ascii=False)
        if key not in merged:
            unique={json.dumps([s.get('moment_id'),s.get('component'),s.get('path'),s.get('value')],sort_keys=True,ensure_ascii=False):s for s in sources}
            item['sources']=list(unique.values());item['issue_id']='issue_'+digest(key)[:16];item['property_ids']=[]
            merged[key]=item
        target=merged[key]
        if pid and pid not in target['property_ids']:target['property_ids'].append(pid)
        if status=='FAIL':target['property_failure']=True
        return target['issue_id']
    for issue in issues:add(issue)
    for prop in properties.get('results',[]):
        pid=prop['property_id'];links[pid]=[]
        if prop['status'] not in ('FAIL','UNKNOWN','NOT_CHECKED') or prop.get('informational'):continue
        findings=[c for c in prop.get('checks',[]) if c.get('code') and c.get('code') not in SOURCE_CODES]
        if not findings and pid in ('A1','A2','A4'):
            equivalent={'A1':'JUSTIFICATION_CONTRADICTION','A2':'REQUIRED_CONDITION_MISSING','A4':'CAN_ACTION_CONTRADICTION'}[pid]
            findings=[i for i in issues if i['code']==equivalent and all(s in prop.get('sources',[]) for s in i.get('sources',[]))]
        if not findings:
            findings=[{'code':pid if prop.get('sources') else 'PROPERTY_INPUT_REQUIRED','message':prop['message'],'sources':prop.get('sources',[])}]
        for finding in findings:
            iid=add(finding,pid,prop['status'])
            if iid not in links[pid]:links[pid].append(iid)
    frames={m['frame']['frame_id']:m['frame'] for m in inputs.values() if m.get('frame')}
    can=next((p for p in properties.get('results',[]) if p['property_id']=='A4'),{})
    for item in merged.values():
        item['suggestions']=[]
        if item['code']=='POSTCONDITION_TIMING_REQUIRED':
            item['title']='행동 뒤의 기대 결과를 확인할 시점을 지정하세요.'
            item['guidance']='연결된 제약의 관련 행동과 기대 결과를 확인하세요. 실제로 수행한 행동의 바로 다음 영상에서 판단할 결과라면 아래 편집에서 기대 결과 확인 시점을 지정하세요.'
            item['certainty_guidance']='‘이 내용 수정’으로 해당 제약을 열고 ‘기대 결과 확인 시점’을 선택하세요. 관찰 사실의 확인 상태를 바꾸는 문제가 아닙니다. 수정본 검토 완료 후 재검증하세요. 다음 장면의 결과가 없다면 검사 대기로 남습니다.'
        if item['code']=='ACTION_CONTRADICTION':
            item['guidance']='아래에 연결된 실제 행동과 제약이 동시에 성립할 수 없습니다. 영상에서 행동을 잘못 읽었다면 CoC의 실제 행동을 수정하세요. 행동이 맞다면 제약의 적용 대상, 금지·허용 행동, 조건을 성립시킨 관찰 사실을 확인하세요.'
            item['certainty_guidance']='CoC의 실제 행동 또는 제약·관찰 사실 중 영상과 다른 항목만 수정하세요. 제약 설명 문장만 바꾸면 실행 조건은 바뀌지 않습니다. 수정 후 해당 검토를 완료하고 변경 내용 검사를 누르면 EBLC와 검증을 다시 수행합니다.'
        elif item['code']=='RULE_CONTRADICTION':
            item['guidance']='같은 대상의 행동을 동시에 금지하고 요구하는 제약이 연결되어 있습니다. 각 제약의 적용 대상과 시작·해제 조건을 대조하고, 영상·규칙과 다르게 추출한 제약의 행동 또는 조건을 수정하세요.'
        elif item['code']=='RELATION_CONTRADICTION':
            item['guidance']='연결된 위치 관계가 동시에 성립할 수 없습니다. 예를 들어 A가 B의 왼쪽이고 B도 A의 왼쪽일 수는 없습니다. 영상의 자차 진행 방향을 기준으로 대상 순서와 관계를 확인하여 잘못된 항목을 수정하세요.'
        if item['code']=='EVIDENCE_MISSING':item['guidance']='확인 상태와 연결된 영상 근거를 대조하세요. 영상으로 알 수 없는 사실은 판단할 수 없음으로 남기고, 근거가 없는데 해당하지 않음으로 바꾸어 조건을 해제하지 마세요.'
        elif item['code']=='LIFECYCLE_CONFLICT':
            item['guidance']='현재 시점의 시작·해제 관찰을 먼저 비교하세요. 관찰을 잘못 선택했다면 현재 관찰을 수정합니다. 두 관찰이 모두 맞다면 원래 제약의 적용 범위를 수정해야 합니다. 공사 구역이 계속 막혀 있어도 자차는 그 구역을 완전히 지나칠 수 있으므로, 통과했다는 이유만으로 통행 차단을 해당하지 않음으로 바꾸지 마세요.'
            item['certainty_guidance']='통과 여부를 아직 확인하지 못했다면 현재 관찰을 판단할 수 없음으로, 아직 지나치지 않았음을 확인했다면 해당하지 않음으로 검토하세요. 실제로 완전히 지나쳤다면 통과 완료 관찰을 유지하고, 원래 제약의 시작 조건에 통과 전이라는 적용 범위가 필요한지 검토하세요. 시작·해제 근거가 서로 충돌한다면 연결된 관찰 각각의 상태와 영상을 대조하세요.'
        elif item['code']=='CAN_ACTION_CONTRADICTION':item['guidance']='측정 속도와 실제 행동 선택이 맞는지 확인하세요. 움직이는 동안의 주행 지속과 이미 멈춘 상태의 정지 유지는 다릅니다.'
        elif item['code']=='UNBOUND_TARGET':item['guidance']='제약을 만든 시점의 대상 연결을 확인하세요. 현재 영상에 보이지 않는 대상을 현재 관찰 목록에 추가할 필요는 없습니다.'
        for source in item['sources']:
            owner=inputs.get(source.get('moment_id'),{})
            retained=(models or {}).get(source.get('moment_id'),{}).get('property_input',{}).get('inherited_entities',[])
            entities=retained+owner.get('components',{}).get('sequence_coc',{}).get('payload',{}).get('entities',[])
            source['entity_labels']={e['entity_id']:e.get('description') or e['kind'] for e in entities}
            source['entity_kinds']={e['entity_id']:e['kind'] for e in entities}
            component=owner.get('components',{}).get(source.get('component'),{});payload=component.get('payload',{})
            value=source.get('value') or {}
            original=payload.get('original_candidate')
            parts=source.get('path') or []
            if isinstance(parts,str):parts=parts.lstrip('/').split('/')
            if parts and parts[-1] in ('truth','scope_state','evidence_note'):parts=parts[:-1]
            for part in parts:
                try:original=original[int(part)] if isinstance(original,list) else original[part]
                except (KeyError,TypeError,IndexError,ValueError):original=None;break
            note=value.get('evidence_note') if isinstance(value,dict) else None
            source['provenance']={'input_revision':owner.get('revision'),'component_id':component.get('id'),'generation_job_id':payload.get('generation_job_id'),'note_origin':'MODEL_ORIGINAL' if note and isinstance(original,dict) and original.get('evidence_note')==note else 'REVIEWED_INPUT' if note else None}
            source['linked_frames']=[{'frame_id':f['frame_id'],'asset_id':f.get('asset_id'),'ordinal':f['ordinal'],'timestamp_us':f['timestamp_us'],'temporal_role':'CURRENT' if f['timestamp_us']==owner.get('t0_us') else 'PREVIOUS' if f['timestamp_us']<owner.get('t0_us',f['timestamp_us']) else 'OTHER'} for fid in source.get('evidence_refs',[]) if (f:=frames.get(fid))]
            source['linked_frames'].sort(key=lambda f:f['timestamp_us'])
            atom=value.get('atom',value) if isinstance(value,dict) else {}
            if item['code']=='UNSUPPORTED_ATOM' and atom.get('predicate'):
                from guard_synth.studio_relations import atom_error
                detail=atom_error(atom,{e['entity_id']:e for e in entities})
                if detail:
                    item['title']='관계에 맞는 대상 연결을 확인하세요.'
                    item['guidance']=detail
                    item['certainty_guidance']='대상 연결을 먼저 고치세요. 확인 상태를 해당하지 않음이나 판단할 수 없음으로 바꾸어도 형식 오류는 해결되지 않습니다.'
            if isinstance(value,dict) and (value.get('truth')=='FALSE' or item['code']=='LIFECYCLE_CONFLICT' and value.get('truth')=='TRUE') and any(phrase in value.get('evidence_note','') for phrase in ('확정하기 어렵','판단하기 어렵','확인하지 못','확인되지 않')):
                item['suggestions'].append({'kind':'UNCERTAINTY_REVIEW','source':deepcopy(source),'field':'truth','before':value['truth'],'value':'UNKNOWN','basis':value['evidence_note'],'message':'확인하지 못했다는 근거에 맞춰 확인 상태를 판단할 수 없음으로 바꾸는 후보입니다. 조건이 해제됐다는 뜻이 아니며, 대상 연결이나 다른 조건의 모순은 해결하지 않습니다.'})
            if item['code']=='CAN_ACTION_CONTRADICTION' and source.get('component')=='sequence_coc' and isinstance(value,dict):
                for checked,record in zip(can.get('checks',[]),can.get('sources',[])):
                    if checked.get('status')!='FAIL' or any(record.get(k)!=source.get(k) for k in ('moment_id','component','path','value')):continue
                    replacement={'HOLD':'CONTINUE','CONTINUE':'HOLD'}.get(value.get('code'))
                    if replacement:
                        item['suggestions'].append({'kind':'COUNTEREXAMPLE_CANDIDATE','source':deepcopy(source),'field':'code','before':value['code'],'value':replacement,'basis':checked['message'],'message':'영상에서도 이 행동이 확인되는 경우에 선택하세요. 출발·정지 과정이면 해당 행동을 직접 선택하세요. 이 후보는 행동·CAN 충돌에 대한 제안이며, 전체 제약 통과를 보장하지 않습니다.'})
            if item['code']=='UNSUPPORTED_ATOM' and atom.get('predicate')=='APPLIES_TO':
                subject=next((e for e in entities if e['entity_id']==atom.get('subject_ref')),None)
                if subject and subject['kind']!='SIGNAL':
                    item['title']='적용 여부를 확인할 대상이 잘못 연결되었습니다.'
                    label=subject.get('description') or '선택된 대상'
                    item['guidance']=f'근거 설명은 표지를 말하지만, 현재 적용 관계에는 ‘{label}’이 연결되어 있습니다. 표지와 공사 구역은 서로 다른 대상입니다. 공사 구역을 신호로 바꾸면 다른 관찰도 잘못 연결될 수 있습니다.' if '표지' in value.get('evidence_note','') else f'‘{label}’은 신호 종류가 아닙니다. 적용 관계의 시작 대상에는 실제 신호가 연결되어야 합니다. 영상 근거와 대상 종류를 대조하세요.'
                    item['limitation']='현재 적용 관계는 신호에서 자차·차로·영역으로만 연결할 수 있습니다. 교통 표지 대상은 아직 지원하지 않아 이 표지의 적용성은 현재 모델로 검증할 수 없습니다.'
                    item['certainty_guidance']='판단하기 어렵다는 근거는 ‘해당하지 않음’이 아니라 ‘판단할 수 없음’으로 검토하세요. 확인 상태만 바꿔도 대상 연결 문제는 남습니다.'
    return list(merged.values()),links

def summarize(compiled,result,snapshot):
    inputs={m['id']:m for m in snapshot['moments']}
    models={s['moment_id']:s for s in compiled['scenes']}
    scenes=[]
    for row in result['scenes']:
        mid=row['moment_id'];m=inputs[mid];components=m.get('components',{})
        coc=components.get('sequence_coc',{}).get('payload',{})
        con=components.get('sequence_constraints',{}).get('payload',{})
        model=models.get(mid,{})
        has_coc='sequence_coc' in components;has_con='sequence_constraints' in components
        issues=[]
        def issue(code,message,path=None,component='sequence_constraints',value=None):
            sources=[{'moment_id':mid,'component':component,'path':path,'value':deepcopy(value),'evidence_refs':deepcopy(value.get('evidence_refs',[])) if isinstance(value,dict) else []}] if path else []
            issues.append({'code':code,'message':message,'sources':sources})
        if not has_coc and not has_con:input_status='NOT_CREATED'
        elif not (has_coc and has_con):
            input_status='PARTIAL'
            if not has_coc:issue('MISSING_COC','CoC가 아직 작성되지 않았습니다.','/explanation','sequence_coc')
            if not has_con:issue('MISSING_CONSTRAINTS','제약이 아직 작성되지 않았습니다.','/new_definitions' if 'entities' in coc else '/constraints')
        else:
            if not coc.get('observed_actions'):
                issue('MISSING_OBSERVED_ACTION','CoC 설명은 있지만 실제로 확인한 자차 행동이 비어 있습니다. 영상·CAN을 보고 행동을 선택하세요.','/observed_actions','sequence_coc',[])
            for kind,path,label in [('sequence_coc','/explanation','CoC'),('sequence_constraints','/new_definitions' if 'new_definitions' in con else '/constraints','제약')]:
                if not approved(m,kind):issue('UNREVIEWED_COC' if kind=='sequence_coc' else 'UNREVIEWED_CONSTRAINTS',label+'의 현재 수정본을 확인하고 검토 완료를 눌러 주세요.',path,kind)
            input_status='ACTION_NEEDED' if not coc.get('observed_actions') else 'REVIEW_NEEDED' if issues else 'READY'
        # Preserve actionable verifier findings; source review has one shared panel.
        findings=[deepcopy(item) for item in row.get('review_items',[]) if item['code'] not in SOURCE_CODES and (input_status!='NOT_CREATED' or item['code'] in CONTRADICTIONS)]
        issues.extend(findings)
        handled={x['code'] for x in issues}
        for code in row.get('codes',[]):
            if code in SOURCE_CODES or code in handled:continue
            if input_status=='NOT_CREATED' and code in {'REVIEW_REQUIRED','EVIDENCE_MISSING','UNKNOWN_INPUT','PRIOR_CONTEXT_MISSING','EMPTY_CONSTRAINTS'}:continue
            if code=='REVIEW_REQUIRED' and (input_status!='READY' or findings):continue
            if code=='EVIDENCE_MISSING' and 'constraints' in con:
                missing=[(i,d) for i,d in enumerate(con['constraints']) if legacy_missing(d)]
                for i,d in missing:
                    field='scope_state' if d.get('scope_state')=='UNKNOWN' else 'truth' if d.get('truth') in ('UNKNOWN','CONFLICT') else 'evidence_note'
                    issue(code,f'제약 {i+1}의 적용 여부 또는 현재 관찰 근거를 확인하세요.',f'/constraints/{i}/{field}',value=d)
                if missing:continue
            issue(code,'검토할 제약이 비어 있습니다.' if code=='REVIEW_REQUIRED' else None,'/observed_actions' if code=='ACTION_CONTRADICTION' else None,'sequence_coc' if code=='ACTION_CONTRADICTION' else 'sequence_constraints',coc.get('observed_actions') if code=='ACTION_CONTRADICTION' else None)
        issues,property_issue_ids=unified_issues(issues,row.get('properties',{}) if input_status!='NOT_CREATED' else {},inputs,models)
        raw_codes=row.get('codes',[])
        if row['status']=='CONTRADICTION' or any(i['code'] in CONTRADICTIONS or i.get('property_failure') for i in issues):display='CONTRADICTION'
        elif input_status=='NOT_CREATED':display='NOT_CREATED'
        elif issues or input_status!='READY':display='REVIEW_REQUIRED'
        elif row['status']=='PASS':display='PASS'
        elif set(raw_codes).issubset(SOURCE_CODES):display='SOURCE_REVIEW'
        else:display='REVIEW_REQUIRED'
        scenes.append({'moment_id':mid,'ordinal':row['ordinal'],'input_status':input_status,'display_status':display,'raw_status':row['status'],'raw_codes':deepcopy(raw_codes),'issues':issues,'property_issue_ids':property_issue_ids,'observed_actions':deepcopy(coc.get('observed_actions',[])),'carried_ids':sorted(model.get('ledger',{})),'ledger':deepcopy(model.get('ledger',{}))})
    by_ordinal={s['ordinal']:s for s in scenes}
    pairs=[]
    for p in result.get('pairs',[]):
        a,b=by_ordinal.get(p['from_ordinal']),by_ordinal.get(p['to_ordinal'])
        ready=bool(a and b and a['input_status']=='READY' and b['input_status']=='READY')
        codes=[c for c in p.get('codes',[]) if c not in SOURCE_CODES]
        # Pending pair input does not erase a reported contradiction.
        state='CONTRADICTION' if p['status']=='CONTRADICTION' else 'SOURCE_REVIEW' if ready and p['status']=='REVIEW_REQUIRED' and not codes else p['status'] if ready else 'WAITING'
        pairs.append({'from_ordinal':p['from_ordinal'],'to_ordinal':p['to_ordinal'],'status':state,'ready':ready,'codes':codes if ready or state=='CONTRADICTION' else [],'carried_ids':deepcopy(p.get('carried_ids',[]))})
    def grouped(rows,key):
        groups=[]
        for r in rows:
            signature=key(r)
            adjacent=groups and (r['ordinal']==groups[-1]['to_ordinal']+1 if 'ordinal' in r else r['from_ordinal']==groups[-1]['to_ordinal'])
            if adjacent and signature==groups[-1]['signature']:
                groups[-1]['to_ordinal']=r.get('ordinal',r.get('to_ordinal'));groups[-1]['count']+=1
            else:
                groups.append({**deepcopy(r),'from_ordinal':r.get('ordinal',r.get('from_ordinal')),'to_ordinal':r.get('ordinal',r.get('to_ordinal')),'count':1,'signature':signature})
        for g in groups:g.pop('signature')
        return groups
    def scene_key(r):
        # Never merge different actions, conditions, verdicts, or review issues.
        return json.dumps([r['input_status'],r['display_status'],r['observed_actions'],r['ledger'],[(x['code'],x['message'],[(s['component'],s['path'],s['value']) for s in x['sources']]) for x in r['issues']]],sort_keys=True,ensure_ascii=False)
    notices=[]
    if any(set(s['raw_codes'])&SOURCE_CODES or models.get(s['moment_id'],{}).get('source_status')=='REVIEW_REQUIRED' for s in scenes):
        notices.append({'code':'SOURCE_REVIEW','message':'규칙 원문·출처 검토가 완료되지 않았습니다. 장면의 논리 검사와 별도로 확인해야 합니다.','condition_ids':sorted({d['condition_id'] for m in models.values() for d in m.get('constraints',[]) if not d.get('source_refs')})})
    authored=[s for s in scenes if s['input_status']!='NOT_CREATED']
    counts={'total':len(scenes),'authored':len(authored),'not_created':len(scenes)-len(authored),'ready':sum(s['input_status']=='READY' for s in scenes),'contradictions':sum(s['display_status']=='CONTRADICTION' for s in scenes),'checked_pairs':sum(p['ready'] for p in pairs),'pending_pairs':sum(not p['ready'] for p in pairs)}
    counts['authored_results']={'total':len(authored),'pass':sum(s['raw_status']=='PASS' for s in authored),'contradiction':sum(s['raw_status']=='CONTRADICTION' for s in authored),'review_required':sum(s['raw_status']=='REVIEW_REQUIRED' for s in authored),'pass_rate':sum(s['raw_status']=='PASS' for s in authored)/len(authored) if authored else None}
    return {'counts':counts,'source_notices':notices,'scenes':scenes,'scene_groups':grouped(scenes,scene_key),'pair_groups':grouped(pairs,lambda p:(p['status'],p['ready'],tuple(p['codes']),tuple(p['carried_ids']))),'raw_verdicts_preserved':True}
