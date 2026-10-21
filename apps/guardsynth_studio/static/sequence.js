'use strict';
(()=>{
 const names={START:'출발',STOP:'정지 행동',CONTINUE:'주행 지속',ENTER:'영역 진입',HOLD:'정지 유지'};
 const statuses={PASS:'입력 조건 안에서 일치',REVIEW_REQUIRED:'확인 필요',CONTRADICTION:'모순 발견'};
 const messages={ACTION_CONTRADICTION:'관찰 행동이 유지 중인 조건과 맞지 않습니다.',RULE_CONTRADICTION:'같은 시점의 제약끼리 충돌합니다.',IDENTITY_CONFLICT:'이전 장면과 같은 조건의 의미가 달라졌습니다.',OBSERVATION_CONFLICT:'관찰 근거끼리 충돌합니다.',EVIDENCE_MISSING:'조건의 해제 또는 유지 여부를 확인할 근거가 부족합니다.',REVIEW_REQUIRED:'CoC·제약 또는 관찰 행동의 검토가 필요합니다.',POSSIBLE_OMISSION:'관련 행동의 규칙 조건이 빠졌을 수 있습니다.',CATALOG_MISSING:'규칙 원문이 연결되지 않았습니다.',UNGROUNDED:'제약의 규칙 출처가 확인되지 않았습니다.',OBSERVATION_GAP:'시점 사이 관찰 공백이 있습니다.',SOLVER_UNKNOWN:'검사 결과를 결정하지 못했습니다.'};
 Object.assign(messages,{RELATION_CONTRADICTION:'대상 사이의 관계 방향이 서로 맞지 않습니다.',POSTCONDITION_CONTRADICTION:'행동 뒤의 관찰이 예상한 결과와 다릅니다.',POSTCONDITION_UNKNOWN:'행동 뒤의 결과를 확인할 관찰이 부족합니다.',PRECONDITION_CONTRADICTION:'행동 전에 필요한 사실과 관찰이 맞지 않습니다.',PRECONDITION_UNKNOWN:'행동 전에 필요한 사실을 확인하지 못했습니다.',LIFECYCLE_CONFLICT:'조건이 시작되거나 끝나는 근거끼리 충돌합니다.',PRIOR_CONTEXT_MISSING:'바로 이전 시점이 없어 출발 여부를 확인할 수 없습니다.',UNKNOWN_INPUT:'확인되지 않은 관찰이 남아 있습니다.',UNRESOLVED_PREVIOUS:'이전 조건이 해제되었는지 확인하지 못했습니다.',UNSUPPORTED_CONDITION:'현재 검사에서 다룰 수 없는 조건이 있습니다.',LEGACY_INPUT_GAP:'이전 형식의 입력에는 대상과 관계 정보가 부족합니다.',HUMAN_ASSISTED_PAIR:'CoC를 사람이 고친 뒤 만든 제약이므로 모델만의 첫 제안과 구분합니다.',INVALID_ORIGINAL:'모델 첫 제안의 입력을 검사할 수 없습니다.',NO_MODERN_GENERATION_PAIR:'아직 대상·관계가 포함된 모델 생성 쌍이 없습니다.',CURRENT_REVIEW_REQUIRED:'현재 입력의 검토와 검증이 필요합니다.',ORIGINAL_QUALITY_PENDING:'모델 첫 제안의 최초 검사 결과가 아직 준비되지 않았습니다.'});
 let coc=null,bundle=null,view=null,token=0,dirty=false,cocReviewPath=null,cocReviewMoment=null,editorSource=null,rendering=Promise.resolve(),resumedJob=null;
 const approved=kind=>{const m=state.moment,c=m?.components[kind],a=m?.approvals[kind],d=view?.input_diagnostics?.[m?.id];return !!c&&!c.stale&&a?.decision==='APPROVE'&&a.component_id===c.id&&!d?.format_errors?.[kind]?.length&&!(kind==='sequence_constraints'&&d?.constraint_binding);};
 let reviewDraft=null,applyingReview=false;
 const draftKey=()=>state.moment?'guardsynth:review:'+state.actor+':'+state.moment.id:null;
 function draftChanged(){return !!reviewDraft&&['sequence_coc','sequence_constraints'].some(k=>canonical(reviewDraft.base[k])!==canonical(k==='sequence_coc'?coc:bundle));}
 function rememberDraft(){
  if(!reviewDraft||applyingReview)return;
  reviewDraft.values={sequence_coc:clone(coc),sequence_constraints:clone(bundle)};
  try{sessionStorage.setItem(draftKey(),JSON.stringify(reviewDraft));}catch(e){error(new Error('브라우저에 수정 초안을 보관하지 못했습니다. 창을 닫기 전에 수정 반영을 누르세요.'));}
 }
 function beginReviewDraft(){
  if(reviewDraft)return;
  reviewDraft={revision:state.moment.revision,base:{sequence_coc:clone(coc),sequence_constraints:clone(bundle)},values:{sequence_coc:clone(coc),sequence_constraints:clone(bundle)}};
 }
 async function openBatchSource(source,momentId){
  if(state.busy)return;
  if(source.moment_id&&source.moment_id!==state.moment.id){
   if(draftChanged())throw new Error('현재 장면의 수정을 먼저 반영하거나 취소한 뒤 이전 장면을 여세요.');
   reviewDraft=null;
  }
  await openReviewSource({...source,batch:true},momentId);
 }
 function batchPanel(){
  const host=$('seq_batch_review'),changed=draftChanged(),conflict=changed&&reviewDraft.revision!==state.moment?.revision;
  host.hidden=!changed&&!applyingReview;
  $('seq_batch_status').textContent=applyingReview?'수정을 저장하고 검토를 반영하는 중입니다.':conflict?'저장본이 다른 곳에서 바뀌었습니다. 아래 초안을 보존했습니다. 내용을 확인하고 수정 취소를 누른 뒤 최신 입력에서 다시 수정하세요.':'수정 초안 · 아직 저장본과 검사 결과에 반영되지 않았습니다.';
  const list=$('seq_batch_changes');list.replaceChildren();
  if(changed)for(const kind of ['sequence_coc','sequence_constraints']){
   const value=kind==='sequence_coc'?coc:bundle,base=reviewDraft.base[kind];
   for(const [key,items] of Object.entries(value)){
    if(canonical(items)===canonical(base[key]))continue;
    if(Array.isArray(items)){for(const [i,item] of items.entries())if(canonical(item)!==canonical(base[key]?.[i])){const li=el('li',(kind==='sequence_coc'?'CoC':'제약')+' · '+readableStatement(item,refs())+(item.truth?' · '+truths[item.truth]:''));if(item.evidence_note)li.append(el('small',' · 근거: '+item.evidence_note));list.append(li);}if(items.length<(base[key]?.length||0))list.append(el('li',(kind==='sequence_coc'?'CoC':'제약')+' · '+key+' 삭제'));}
    else list.append(el('li',(kind==='sequence_coc'?'CoC 설명':'제약 설명')+' · '+lines(items)));
   }
  }
  const issues=[...relationErrors('sequence_coc'),...relationErrors('sequence_constraints')],invalid=issues.length>0;
  for(const id of ['seq_apply_review','seq_apply_verify'])$(id).disabled=!changed||conflict||state.busy||invalid||!view;
  $('seq_discard_review').disabled=state.busy;
  if(invalid&&changed){$('seq_batch_status').textContent+=` 대상·관계 ${issues.length}개를 확인하세요. 아래 연결 수정 버튼으로 바로 고칠 수 있습니다.`;
   for(const issue of issues){const li=el('li',`${issue.source.component==='sequence_coc'?'CoC':'제약'} · ${reviewLocation(issue.source)}: ${issue.message}`),edit=editButton('대상·관계 수정',()=>openBatchSource({...issue.source,formatError:true}));edit.dataset.batchFormat=issue.source.component+issue.source.path;edit.disabled=state.busy;li.append(edit);list.append(li);}
  }
  if(changed&&!view)$('seq_batch_status').textContent+=' 연결된 대상 정보를 불러오는 중입니다.';
 }
 async function applyReviewDraft(recheck=false){
  if(!draftChanged())return;
  if(reviewDraft.revision!==state.moment.revision)throw new Error('저장본이 바뀌어 수정을 반영하지 않았습니다. 초안과 최신 입력을 대조하세요.');
  const preservedDraft=clone(reviewDraft),storageKey=draftKey(),target=editorSource?.review_moment_id,values={sequence_coc:clone(coc),sequence_constraints:clone(bundle)},changed=['sequence_coc','sequence_constraints'].filter(k=>canonical(values[k])!==canonical(reviewDraft.base[k]));
  applyingReview=true;batchPanel();
  try{
   for(const kind of ['sequence_coc','sequence_constraints']){
    // A CoC edit also needs an explicit rebind and review of the retained constraints.
    if(!changed.includes(kind)&&!(kind==='sequence_constraints'&&changed.includes('sequence_coc')&&state.moment.components.sequence_constraints))continue;
    const unchanged=!!original(kind)&&canonical(values[kind])===canonical(project(original(kind),kind));
    await queue(kind,{...values[kind],accepted_unchanged:unchanged});await flush();
    await approve(kind,'APPROVE');await rendering;
   }
   sessionStorage.removeItem(draftKey());reviewDraft=null;editorSource=null;
   await render();showStage(4);
   $('seq_batch_feedback').textContent='수정을 저장하고 반영했습니다. 최신 입력으로 다시 검증하세요.';
   if(recheck){const completed=await rerunDerived(target);$('seq_batch_feedback').textContent=completed?'수정한 입력으로 검증을 완료했습니다.':'이전 제약의 수정을 반영했습니다. 현재 장면의 CoC와 제약을 다시 확인한 뒤 검증하세요.';}
  }catch(e){reviewDraft=preservedDraft;coc=clone(preservedDraft.values.sequence_coc);bundle=clone(preservedDraft.values.sequence_constraints);sessionStorage.setItem(storageKey,JSON.stringify(preservedDraft));reviewEditor();throw e;}finally{applyingReview=false;batchPanel();}
 }
 const rearmed=new Map(),repeatButtons=[['seq_generate_coc','seq_reset_coc','sequence_coc'],['seq_generate_constraints','seq_reset_constraints','sequence_constraints'],['seq_generate_eblc','seq_reset_eblc','eblc'],['seq_check','seq_reset_verify','verification']];
 function displayProse(text){
  if(typeof text!=='string')return text;
  const frames=[...(state.moment?.frames||[]),...(data('sequence_coc').input_manifest||[]),...(data('sequence_constraints').input_manifest||[])];
  for(const f of frames){const id=f.frame_id;if(!id)continue;const escaped=id.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
   text=text.replace(new RegExp('\\s*\\(\\s*'+escaped+'\\s*\\)','g'),'').split(id).join(`영상 ${(f.timestamp_us/1e6).toFixed(3)}초`);}
  return text;
 }
 function editExplanation(value){
  for(const b of coc.reason_bindings||[]){const excerpt=displayProse(b.explanation_excerpt);if(excerpt!==b.explanation_excerpt&&value.includes(excerpt))b.explanation_excerpt=excerpt;}
  coc.explanation=value;
 }
 const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=tag==='pre'?text:displayProse(text);return e;};
 function original(kind){return data(kind).original_candidate;}
 function same(kind){return !!original(kind)&&canonical(kind==='sequence_coc'?coc:bundle)===canonical(project(original(kind),kind));}
 function structured(p,kind){return kind==='sequence_coc'?Array.isArray(p.entities):Array.isArray(p.new_definitions);}
 function project(p,kind){
  const v2=structured(p,kind),fields=kind==='sequence_coc'?(v2?['entities','relations','observations','observed_actions','explanation','unknowns','evidence_refs']:['observations','observed_actions','explanation','unknowns','evidence_refs']):(v2?['new_definitions','facts','unresolved_previous_condition_refs','unknowns']:['constraints']);
  // Candidate keys, including optional fields, survive editing; provenance is server-owned.
  for(const k of Object.keys(p.original_candidate||{}))if(!fields.includes(k))fields.push(k);
  if(v2&&kind==='sequence_coc')for(const k of ['reason_bindings','action_observation_complete'])if(Object.hasOwn(p,k)&&!fields.includes(k))fields.push(k);
  return Object.fromEntries(fields.map(k=>[k,clone(p[k]??(['observations','explanation'].includes(k)||(!v2&&k==='unknowns')?'':[]))]));
 }
 function canonical(v){return JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);}
 function current(label){const s=view?.stages?.[label];return !!s&&s.job_status==='SUCCEEDED'&&!s.stale&&!dirty;}
 function inputStep(){
  const m=state.moment;if(!m)return {stage:1,text:'영상과 판단 시점을 선택하세요.'};
  if(dirty)return {stage:state.stage,text:'변경 내용을 저장하고 있습니다.'};
  if(!m.components.sequence_coc)return {stage:1,text:'CoC를 먼저 생성하세요.'};
  if(!approved('sequence_coc'))return {stage:1,text:'CoC 검토를 완료하세요. 수정한 행동·문장을 확인한 뒤 검토 완료를 누르세요.'};
  if(!m.components.sequence_constraints||view?.input_diagnostics?.[m.id]?.constraint_generation)return {stage:2,text:'현재 CoC로 제약을 새로 생성하고 검토하세요.'};
  if(!approved('sequence_constraints'))return {stage:2,text:'제약 검토를 완료하세요. 현재 CoC에 맞는지 확인한 뒤 검토 완료를 누르세요.'};
  return {stage:3,text:current('eblc')?'현재 EBLC로 검증을 실행하세요.':'검토가 완료되었습니다. EBLC를 생성한 뒤 검증하세요.'};
 }
 const entityCocReady=()=>Array.isArray(coc?.entities)&&coc.entities.some(e=>e.entity_id==='ego'&&e.kind==='EGO');
 function relationErrors(kind){
  const rules=view?.relation_grammar?.rules;if(!rules)return (view?.input_diagnostics?.[state.moment?.id]?.format_errors?.[kind]||[]).map(e=>({message:e.message,source:{moment_id:state.moment?.id,component:kind,path:e.path}}));
  const p=kind==='sequence_coc'?coc:bundle;
  const entities=Object.fromEntries(contextEntities().map(e=>[e.entity_id,e.kind]));
  const atoms=kind==='sequence_coc'?[...(p?.relations||[]).map((v,i)=>({a:v,path:`/relations/${i}`,value:v})),...(p?.reason_bindings||[]).flatMap((b,i)=>b.reasons.map(g=>({a:g.atom,path:`/reason_bindings/${i}`,value:b})))]:[...(p?.facts||[]).map((v,i)=>({a:v.atom,path:`/facts/${i}`,value:v})),...(p?.new_definitions||[]).flatMap((d,i)=>['activation_all_of','release_any_of','preconditions','expected_postconditions'].flatMap(k=>d[k].map(g=>({a:g.atom,path:`/new_definitions/${i}`,value:d}))))];
  const issues=[];
  for(const {a,path,value} of atoms){const r=rules[a.predicate];let message;
   if(!r)message='지원하지 않는 확인 관계입니다.';
   else if(!entities[a.subject_ref])message='관찰 대상 정보를 찾을 수 없습니다. 연결된 대상을 확인하세요.';
   else if(!r.subject_kinds.includes(entities[a.subject_ref]))message='관찰 대상의 종류와 확인할 관계가 맞지 않습니다.';
   else if(r.arity==='UNARY'&&a.object_ref!==null)message='한 대상의 상태를 확인하는 항목입니다. 불필요한 비교 대상을 제거하세요.';
   else if(r.arity==='BINARY'&&!a.object_ref)message='이 관계에는 비교·적용 대상이 필요합니다.';
   else if(a.object_ref&&!entities[a.object_ref])message='비교·적용 대상 정보를 찾을 수 없습니다. 연결된 대상을 확인하세요.';
   else if(a.object_ref&&!r.object_kinds.includes(entities[a.object_ref]))message='비교·적용 대상의 종류와 확인할 관계가 맞지 않습니다.';
   if(message)issues.push({message,source:{moment_id:state.moment?.id,component:kind,path,value:clone(value)}});
  }
  return issues;
 }
 const invalidRelations=kind=>relationErrors(kind).length>0;
 function completedRun(kind){
  const m=state.moment;if(!m)return null;
  if(kind==='sequence_constraints'&&view?.input_diagnostics?.[m.id]?.constraint_generation)return null;
  const c=m.components[kind],id=c?(!c.stale?c.id:null):current(kind)?view.stages[kind].job_id:null;
  return id?m.id+':'+id:null;
 }
 function controls(){
  const m=state.moment,busy=state.busy||state.navigationPending!==null;
  const bindingGap=view?.input_diagnostics?.[m?.id]?.constraint_binding;
  $('seq_generate_coc').disabled=!m||busy||!m.generation?.enabled;
  $('seq_generation_reason').textContent=m?.generation?.reason||'';
  const formatGap=!!m?.components.sequence_coc&&!entityCocReady(),generationGap=formatGap&&state.capabilities?.provider_mode==='REAL';
  $('seq_generate_constraints').disabled=!m||busy||dirty||!m.generation?.enabled||!approved('sequence_coc')||generationGap;
  $('seq_constraints_generation_reason').textContent=generationGap?'현재 CoC에 장면 대상 정보가 없어 제약 생성을 중단했습니다. 1단계에서 CoC를 다시 생성·검토하세요. 모델 호출은 실행되지 않습니다.':m?.generation?.reason||'';
  $('seq_back_to_coc').hidden=!generationGap;$('seq_back_to_coc').disabled=busy;
  for(const [kind,suffix] of [['sequence_coc','coc'],['sequence_constraints','constraints']]){
   const c=m?.components[kind],accept=$('seq_accept_'+suffix);const unchanged=same(kind);
   accept.disabled=!m||busy||!unchanged||kind==='sequence_constraints'&&!!view?.input_diagnostics?.[m?.id]?.constraint_generation;if(!unchanged)accept.checked=false;
   const formatErrors=view?.input_diagnostics?.[m?.id]?.format_errors?.[kind]||[];
   $('seq_approve_'+suffix).disabled=!c||busy||invalidRelations(kind)||(unchanged&&!accept.checked)||(kind==='sequence_constraints'&&(!!bindingGap||!approved('sequence_coc')||(Array.isArray(bundle?.new_definitions)&&formatGap)));
   $('seq_'+suffix+'_status').textContent=kind==='sequence_constraints'&&bindingGap?bindingGap:formatErrors.length?`관계 형식 ${formatErrors.length}개 확인 필요 · ${formatErrors[0].message}`:c?.stale?(kind==='sequence_coc'?'이전 시점이 수정되었습니다. 현재 CoC를 다시 확인한 뒤 검토 완료를 누르세요.':'CoC가 수정되었습니다. 제약이 현재 CoC에 맞는지 확인한 뒤 검토 완료를 누르세요.'):approved(kind)?'검토 완료':'검토 전';
  }
  $('seq_generate_eblc').disabled=!m||busy||dirty||!view||!approved('sequence_coc')||!approved('sequence_constraints')||(Array.isArray(bundle?.new_definitions)&&formatGap);
  const checking=['QUEUED','RUNNING'].includes(view?.stages?.verification?.job_status);
  $('seq_check').disabled=!m||busy||checking||!current('eblc');$('seq_generate_cnl').disabled=!m||busy||!current('verification');
  const findings=view?.stages?.verification?.review_summary?.scenes.filter(s=>s.input_status!=='NOT_CREATED')||[];
  $('seq_generate_cnl').textContent=current('verification')&&findings.some(s=>!['PASS','SOURCE_REVIEW'].includes(s.display_status))?'확인 항목을 포함한 CNL 초안 생성':'CNL 생성';
  for(const [id,resetId,kind] of repeatButtons){
   const done=completedRun(kind),button=$(id),reset=$(resetId),armed=done&&rearmed.get(id)===done;
   reset.hidden=!done;reset.disabled=button.disabled||!!armed;reset.textContent=kind==='verification'?(armed?'재검증 준비됨':'재검증 준비'):(armed?'재생성 준비됨':'재생성 준비');
   reset.title='기존 결과를 보존하고 실행 버튼만 활성화합니다. 이 버튼은 모델 호출이나 검증을 실행하지 않습니다.';
   if(done&&!armed)button.disabled=true;
  }
  const checked=completedRun('verification'),repeat=checked&&rearmed.get('seq_check')===checked;
  $('seq_check').textContent=checking?'검증 중…':checked&&!repeat?'검증 완료':'검증 실행';
  $('seq_verify_guidance').textContent=!m?'판단 시점을 선택하세요.':checking?'검증이 진행 중입니다. 완료되면 현재 입력의 결과와 확인할 항목이 표시됩니다.':busy?'작업을 처리하고 있습니다. 완료 후 검증 실행 상태가 갱신됩니다.':!view?'검증 준비 상태를 불러오고 있습니다.':dirty?inputStep().text:!current('eblc')?inputStep().text:checked&&!repeat?'현재 입력의 검증이 완료되었습니다. 아래 결과에서 확인할 항목을 검토하세요. 같은 입력을 다시 검사하려면 재검증 준비를 누르세요.':'최신 EBLC가 준비되었습니다. 검증 실행을 누르면 현재 입력의 확인할 항목이 표시됩니다.';
  $('seq_next_verify').disabled=!current('eblc')||busy;$('seq_next_cnl').disabled=!current('verification')||busy;
  $('seq_explanation').disabled=!m||busy;
  for(const b of document.querySelectorAll('.structured_edit'))b.disabled=!m||busy||b.dataset.full==='true';
  for(const x of document.querySelectorAll('#seq_candidates input,#seq_candidates textarea,#seq_candidates select,#seq_coc_fields input,#seq_coc_fields textarea,#seq_coc_fields select,#seq_review_editor input,#seq_review_editor textarea,#seq_review_editor select'))x.disabled=!m||busy;
  for(const b of document.querySelectorAll('#seq_review_editor button'))b.disabled=!m||busy||!!b.dataset.full&&b.dataset.full==='true';
  for(const b of document.querySelectorAll('[data-review-approve]')){const kind=b.dataset.reviewApprove,c=m?.components[kind],d=view?.input_diagnostics?.[m?.id];b.textContent=same(kind)?'원문 수용 · 검토 완료':'이 수정본 검토 완료';b.disabled=!c||busy||invalidRelations(kind)||(kind==='sequence_constraints'&&(!!d?.constraint_binding||!approved('sequence_coc')));}
  for(const b of document.querySelectorAll('[data-keep-unknown]'))b.disabled=busy||draftChanged();
  for(const b of document.querySelectorAll('[data-review-refresh]'))b.disabled=!m||busy||!approved('sequence_coc');
  for(const input of document.querySelectorAll('[data-review-accept]')){input.disabled=busy||!same(input.dataset.reviewAccept)||input.dataset.reviewAccept==='sequence_constraints'&&!!view?.input_diagnostics?.[m?.id]?.constraint_generation;input.checked=$('seq_accept_'+(input.dataset.reviewAccept==='sequence_coc'?'coc':'constraints')).checked;}
  const hints=['','CoC를 생성하고 문장을 검토하세요.','CoC 검토 후 제약을 생성하세요.','제약 검토 후 EBLC를 생성하세요.','생성한 EBLC로 검증하세요.','검증 결과를 CNL 문장으로 확인하세요.'];
  const next=inputStep();$('stage_hint').textContent=draftChanged()?'검증 탭에 모아 둔 수정이 있습니다. 수정 반영 또는 수정 취소를 누르세요.':m?(state.stage>=next.stage&&state.stage>=3?next.text:hints[state.stage]):next.text;
  if(draftChanged())for(const id of ['seq_generate_coc','seq_generate_constraints','seq_approve_coc','seq_approve_constraints','seq_generate_eblc','seq_check','seq_generate_cnl','seq_next_cnl'])$(id).disabled=true;
  if(!dirty&&(current('verification')||view?.stages?.verification?.stale&&approved('sequence_coc')&&approved('sequence_constraints')))$('seq_verify_guidance').textContent='';
  $('seq_recheck_saved').disabled=busy||draftChanged()||!approved('sequence_coc')||!approved('sequence_constraints');
  correctionFlow();pendingConstraintReview();batchPanel();
 }
 function pendingConstraintReview(){
  const m=state.moment,host=$('seq_pending_constraint_review');
  host.hidden=!m||!view||dirty||draftChanged()||!approved('sequence_coc')||!m.components.sequence_constraints||approved('sequence_constraints');
  if(host.hidden)return;
  const content=$('seq_pending_constraint_changes');content.replaceChildren();
  const initial=original('sequence_constraints')||{},labels=refs();
  const changes=el('ul');
  for(const key of ['facts','new_definitions','constraints']){
   for(const value of bundle[key]||[]){if((initial[key]||[]).some(old=>canonical(old)===canonical(value)))continue;
    const truthLabel=value.atom?.predicate==='PASSAGE_COMPLETE'?({TRUE:'이미 완전히 지나쳤음',FALSE:'아직 완전히 지나치지 않았음',UNKNOWN:'영상으로 판단할 수 없음',CONFLICT:'근거 충돌'})[value.truth]:truths[value.truth];
    const item=el('li',readableStatement(value,labels)+(value.truth?' · '+truthLabel:''));
    if(value.evidence_note)item.append(el('p','입력한 근거: '+value.evidence_note));
    if(value.activation_all_of)for(const [field,label] of [['activation_all_of','시작 조건'],['release_any_of','해제 조건'],['preconditions','행동 전 조건'],['expected_postconditions','행동 뒤 기대 결과']])for(const g of value[field]||[])item.append(el('p',`${label}: ${readableStatement(g.atom,labels)} · 필요한 확인 상태 ${truths[g.expected_truth]}`));
    if(value.actions)item.append(el('p',`${value.actions.map(a=>names[a]).join(', ')} · ${effects[value.effect]}`));changes.append(item);
   }
   for(const old of initial[key]||[]){const sameItem=value=>key==='facts'?canonical(value.atom)===canonical(old.atom):value.condition_id===old.condition_id;if(!(bundle[key]||[]).some(sameItem))changes.append(el('li','삭제한 항목: '+readableStatement(old,labels)));}
  }
  if(changes.children.length){content.append(el('p','모델 제안에서 추가·수정·삭제한 내용'),changes);}else{content.append(el('p',same('sequence_constraints')?'현재 수정본은 모델 원문과 같습니다. 아래 원문 수용·검토 완료 버튼을 누르면 이 저장본을 수용하고 재검증합니다. 별도의 수용 체크를 찾을 필요가 없습니다.':'현재 저장본의 검토 승인이 필요합니다. 아래 버튼으로 검토를 완료하고 재검증하세요.'));const index=pendingFactIndex(),f=bundle.facts?.[index];if(f)content.append(el('p',readableStatement(f,labels)+' · '+truths[f.truth]),el('p','저장된 근거: '+f.evidence_note));}
  const diagnostic=view.input_diagnostics?.[m.id],reason=$('seq_pending_constraint_reason');
  reason.textContent=diagnostic?.constraint_generation||diagnostic?.constraint_binding||diagnostic?.format_errors?.sequence_constraints?.[0]?.message||'아래 버튼에서 이 입력을 검토 완료한 뒤 EBLC 재생성 → 검증을 이어서 수행합니다. 모델을 다시 호출하지 않습니다.';
  $('seq_approve_constraints_recheck').textContent=same('sequence_constraints')?'원문 수용·검토 완료 · 재검증':'수정본 검토 완료 · 재검증';
  $('seq_approve_constraints_recheck').disabled=dirty||state.busy||state.navigationPending!==null||invalidRelations('sequence_constraints')||!!diagnostic?.constraint_binding||!!diagnostic?.constraint_generation||!entityCocReady()&&Array.isArray(bundle.new_definitions);
  $('seq_open_pending_constraints').disabled=state.busy||state.navigationPending!==null;
 }
 function pendingFactIndex(){
  const scene=view?.stages?.verification?.review_summary?.scenes.find(s=>s.moment_id===state.moment?.id);
  for(const source of (scene?.issues||[]).flatMap(i=>i.sources||[])){const match=sourcePath(source).match(/^facts\[(\d+)\]$/),index=match&&Number(match[1]);if(source.moment_id===state.moment?.id&&source.component==='sequence_constraints'&&match&&bundle.facts?.[index]&&canonical(bundle.facts[index])!==canonical(source.value))return index;}
  return bundle.facts?.findIndex(f=>!(original('sequence_constraints')?.facts||[]).some(old=>canonical(old)===canonical(f)))??-1;
 }
 function correctionFlow(){
  if(draftChanged()){const host=$('seq_correction_flow');host.hidden=state.stage===4;$('seq_revision_status').textContent='검증 수정 초안이 아직 반영되지 않았습니다.';$('seq_correction_hint').hidden=true;$('seq_resume').hidden=false;$('seq_resume').disabled=state.busy;$('seq_resume').textContent='모아 둔 수정 보기';return;}
  const m=state.moment,v=view?.stages?.verification,host=$('seq_correction_flow');
  const ready=approved('sequence_coc')&&approved('sequence_constraints');
  for(const b of document.querySelectorAll('[data-review-recheck]'))b.disabled=dirty||state.busy||!ready;
  host.hidden=!m||!dirty&&!v?.stale||state.stage===4&&ready;if(host.hidden)return;
  const checked=v?.input_revisions?.[m.id];
  const status=$('seq_revision_status');status.dataset.savedRevision=String(m.revision);status.dataset.checkedRevision=checked===undefined?'':String(checked);
  const next=inputStep();status.textContent=next.text;
  const b=$('seq_resume');b.disabled=dirty||state.busy||state.navigationPending!==null;
  b.textContent=next.stage===1?'CoC 검토하기':next.stage===2?(!m.components.sequence_constraints?'제약 생성하기':'제약 검토하기'):'변경 내용 검사';
  b.hidden=dirty;
  const hint=$('seq_correction_hint');hint.hidden=ready||dirty;
  hint.textContent='';
 }
 async function approveReviewed(kind,acceptOriginal=false){
  if(draftChanged())throw new Error('모아 둔 수정을 먼저 수정 반영으로 저장하세요.');
  if(reviewDraft){sessionStorage.removeItem(draftKey());reviewDraft=null;}
  const diagnostics=view?.input_diagnostics?.[state.moment.id];
  if(kind==='sequence_constraints'&&diagnostics?.constraint_binding)throw new Error(diagnostics.constraint_binding);
  if(acceptOriginal&&same(kind)&&!$('seq_accept_'+(kind==='sequence_coc'?'coc':'constraints')).checked){$('seq_accept_'+(kind==='sequence_coc'?'coc':'constraints')).checked=true;await save(kind);await flush();}
  if(state.moment.components[kind]?.stale){await save(kind);await flush();}
  await approve(kind,'APPROVE');await rendering;
 }
 async function rerunDerived(reviewMomentId){
  if(reviewMomentId&&reviewMomentId!==state.moment.id){
   if(!approved('sequence_coc')||!approved('sequence_constraints'))throw new Error('수정한 시점의 CoC와 제약 검토를 먼저 완료하세요.');
   await loadMoment(reviewMomentId);await render();showStage(4);
   if(!approved('sequence_coc')||!approved('sequence_constraints')){showStage(inputStep().stage);controls();return false;}
  }
  const momentId=state.moment.id,extraction=state.moment.extraction_id;
  if(!approved('sequence_coc')||!approved('sequence_constraints'))throw new Error('수정한 CoC와 제약의 검토를 먼저 완료하세요.');
  for(const path of ['sequence-eblc','sequence-verify']){
   if(state.moment.id!==momentId)throw new Error('시점이 변경되어 실행을 중단했습니다.');
   const j=await api(`/extractions/${extraction}/${path}`,'POST',{});await pollJob(j.job_id);await rendering;
  }
  const checked=view?.stages?.verification;
  const authored=checked?.review_summary?.scenes.filter(s=>s.input_status!=='NOT_CREATED')||[];
  const consistent=authored.length?authored.every(s=>s.display_status==='PASS'||s.display_status==='SOURCE_REVIEW'):checked?.result?.status==='PASS';
  if(consistent){const j=await api(`/extractions/${extraction}/sequence-cnl`,'POST',{});await pollJob(j.job_id);await rendering;}
  showStage(4);renderDerived();return true;
 }
 async function committed(){
  const m=state.moment;if(!m)return;const request=++token,revision=m.revision;
  const loaded=await api(`/extractions/${m.extraction_id}/sequence`);
  if(request!==token||state.moment?.id!==m.id||state.moment.revision!==revision)return;
  if(canonical(coc)!==canonical(project(data('sequence_coc'),'sequence_coc'))||canonical(bundle)!==canonical(project(data('sequence_constraints'),'sequence_constraints')))return;
  view=loaded;dirty=false;refreshForms();renderDerived();controls();
 }
 async function save(kind){
  if(reviewDraft&&!applyingReview){rememberDraft();cocSummary();classOverview();batchPanel();controls();return;}
  const generationGap=view?.input_diagnostics?.[state.moment?.id]?.constraint_generation;
  if(kind==='sequence_constraints'&&generationGap)throw new Error(generationGap);
  if(!state.moment)return;const invalidate=!dirty&&structured(bundle,'sequence_constraints')&&currentCompiled();dirty=true;if(invalidate)refreshForms();if(kind==='sequence_coc')cocSummary();else classOverview();renderDerived();
  const suffix=kind==='sequence_coc'?'coc':'constraints';if(!same(kind))$('seq_accept_'+suffix).checked=false;
  await queue(kind,{...clone(kind==='sequence_coc'?coc:bundle),accepted_unchanged:$('seq_accept_'+suffix).checked});controls();
 }
 async function work(fn){if(state.busy)return;state.busy=true;$('error').textContent='';updateActions();controls();try{await flush();await fn();}finally{try{await rendering;}finally{state.busy=false;updateActions();controls();}}}
 $('seq_explanation').oninput=()=>{if(coc){editExplanation($('seq_explanation').value);save('sequence_coc').catch(error);}};
 for(const suffix of ['coc','constraints'])$('seq_accept_'+suffix).onchange=()=>save('sequence_'+suffix).catch(error);
 function legacyCards(){
  const host=$('seq_candidates');host.replaceChildren();
  if(!bundle?.constraints.length){host.append(el('p',data('sequence_constraints').original_candidate?'생성된 제약이 없습니다. 검토하고 다음 단계에서 확인하세요.':'아직 생성된 제약이 없습니다.'));return;}
  const groups=scopeGroups(host,bundle.constraints);
  bundle.constraints.forEach((c,i)=>{
   const card=el('div');card.className='sequence_condition';card.dataset.conditionId=c.condition_id;card.append(el('h3',`제약 ${i+1}`));scopeBadge(card,c);
   const classification=el('div');classification.className='constraint_class_field';card.append(classification);field(classification,c,'condition_class','제약 분류',`constraints[${i}].condition_class`,{'':'분류 미지정',...classes},{nullable:true});
   const pair=el('div');pair.className='seq_pair';const originalText=original('sequence_constraints')?.constraints.find(x=>x.condition_id===c.condition_id)?.description||c.description;
   const input=el('textarea');input.rows=3;input.value=c.description;input.setAttribute('aria-label',`제약 ${i+1} 설명 수정`);input.oninput=()=>{c.description=input.value;save('sequence_constraints').catch(error);};pair.append(el('pre',originalText),input);card.append(pair);
   const related=c.actions.map(a=>names[a]).join(', ');card.append(el('p',`조건이 있을 때: ${related} ${c.effect==='FORBID'?'허용하지 않음':'요구'}`));
   card.append(el('p',`현재: ${({TRUE:'조건 있음',FALSE:'조건 없음 확인',UNKNOWN:'미확인',CONFLICT:'근거 충돌'})[c.truth]} · ${({IN_SCOPE:'적용 범위 안',ENDED:'적용 범위 종료 확인',UNKNOWN:'적용 범위 미확인'})[c.scope_state]}`));
   const details=el('details');details.append(el('summary','발동·유지·해제 근거'));for(const [label,k] of [['발동','activation'],['유지','hold'],['해제','release'],['관찰 근거','evidence_note']])details.append(el('p',`${label}: ${c[k]}`));card.append(details);
   const observation=section(card,'현재 관찰·적용 여부 수정','영상에서 확인한 경우에만 바꾸세요. 대상이 가려졌다는 이유로 조건이 끝났다고 선택하면 안 됩니다.');
   const grid=row(observation);field(grid,c,'truth','이 조건이 현재 성립하나요?',`constraints[${i}].truth`,{TRUE:'조건 성립 확인',FALSE:'조건이 성립하지 않음을 확인',UNKNOWN:'영상에서 확인하지 못함',CONFLICT:'관찰 근거가 서로 다름'});
   field(grid,c,'scope_state','이 제약이 적용되는 상황인가요?',`constraints[${i}].scope_state`,{IN_SCOPE:'적용되는 상황이 계속됨',ENDED:'적용 상황이 끝났음을 확인',UNKNOWN:'적용 여부를 확인하지 못함'});
   field(observation,c,'evidence_note','확인한 영상·CAN 근거',`constraints[${i}].evidence_note`);groups[conditionScope(c).group].append(card);
  });
 }
 const truths={TRUE:'해당함',FALSE:'해당하지 않음',UNKNOWN:'판단할 수 없음',CONFLICT:'근거 충돌'};
 const effects={FORBID:'행동 금지',REQUIRE:'행동 필요',ALLOW:'행동 허용'};
 const kinds={EGO:'자차',VEHICLE:'차량',PEDESTRIAN:'보행자',CYCLIST:'자전거',SIGNAL:'신호',ZONE:'영역',LANE:'차로',OBSTACLE:'장애물',SURFACE:'노면',VISIBILITY:'시야'};
 const identities={NEW_LOCAL:'현재 장면에서 새로 확인',MATCHED_PREVIOUS:'이전 대상과 같음',UNCERTAIN:'같은 대상인지 미확인'};
 const classes={TRAFFIC_CONTROL:'신호·교통 통제',VEHICLE:'다른 차량',VULNERABLE_ROAD_USER:'보행자·자전거',ROAD_LAYOUT:'도로 구조',WORKZONE_OBSTACLE:'공사·장애물',ROAD_SURFACE:'노면 상태',VISIBILITY:'시야'};
 const classExamples={TRAFFIC_CONTROL:'예: 신호 색, 통행 우선순위',VEHICLE:'예: 선행·후행·합류·추월 차량',VULNERABLE_ROAD_USER:'예: 횡단 보행자, 자전거 접근',ROAD_LAYOUT:'예: 차로 경계, 교차로, 진입 영역',WORKZONE_OBSTACLE:'예: 공사 차단물, 경로의 장애물',ROAD_SURFACE:'예: 젖은 노면, 미끄러짐 위험',VISIBILITY:'예: 가림, 확인할 수 없는 진행 경로'};
 function currentCompiled(){const s=view?.stages?.eblc;return !dirty&&s?.job_status==='SUCCEEDED'&&!s.stale?s.result.scenes.find(r=>r.moment_id===state.moment?.id):null;}
 function conditionScope(d){
  if(Array.isArray(d.activation_all_of)){
   const row=currentCompiled(),info=row?.states?.[d.condition_id],phase=info?.state||row?.ledger?.[d.condition_id];
   if(!row)return {group:'PENDING',label:'적용 상태 계산 전 · EBLC 생성 필요'};
   if(phase==='ACTIVE')return {group:'ACTIVE',label:'적용 중'};
   if(['RELEASED','INACTIVE'].includes(phase))return {group:'NOT_ACTIVE',label:phase==='RELEASED'?'해제 확인':'현재 비활성'};
   return {group:'UNCERTAIN',label:phase==='CONFLICT'?(info?.active_obligation?'근거 충돌 · 이전 조건 유지':'근거 충돌'):'적용 미확인'};
  }
  const valid=d.evidence_refs?.length&&d.evidence_note?.trim();
  if(valid&&d.truth!=='CONFLICT'){
   if(d.scope_state==='ENDED')return {group:'NOT_ACTIVE',label:'구간 종료'};
   if(d.scope_state==='IN_SCOPE'&&d.truth==='FALSE')return {group:'NOT_ACTIVE',label:'해제 확인'};
   if(d.scope_state==='IN_SCOPE'&&d.truth==='TRUE')return {group:'ACTIVE',label:'적용 중 · 입력 기준'};
  }
  return {group:'UNCERTAIN',label:d.truth==='CONFLICT'?'근거 충돌':'적용 미확인'};
 }
 function scopeBadge(card,d){const s=conditionScope(d),badge=el('p',s.label);badge.className='condition_scope_badge';badge.dataset.scopeStatus=s.group;card.dataset.scopeStatus=s.group;card.append(badge);}
 function scopeGroups(host,definitions){
  const groups={},labels={ACTIVE:'적용 중',PENDING:'적용 상태 계산 전',UNCERTAIN:'적용 미확인',NOT_ACTIVE:'현재 적용 안함 · 해제/구간 종료'},notes={ACTIVE:'현재 행동을 검토할 때 함께 확인할 조건입니다.',PENDING:'최신 EBLC가 없어 적용 상태를 아직 계산하지 않았습니다. 입력을 검토한 뒤 EBLC를 생성하세요.',UNCERTAIN:'적용 여부를 확인할 근거가 부족합니다. 이전 조건은 종료 근거 없이 없애지 않습니다.',NOT_ACTIVE:'종료·해제된 조건과 현재 비활성인 후보입니다. 이전 기록은 보존합니다.'};
  for(const key of Object.keys(labels)){
   const count=definitions.filter(d=>conditionScope(d).group===key).length;if(!count)continue;const group=el(key==='NOT_ACTIVE'?'details':'div');group.className='condition_scope_group';group.dataset.scopeGroup=key;group.dataset.group='scope:'+key;group.append(el(key==='NOT_ACTIVE'?'summary':'h3',`${labels[key]} · ${count}개`));group.append(el('p',notes[key]));host.append(group);groups[key]=group;
  }return groups;
 }
 function displayedDefinitions(){if(view?.input_diagnostics?.[state.moment?.id]?.constraint_generation)return [];const local=structured(bundle,'sequence_constraints')?bundle.new_definitions:(bundle?.constraints||[]),ids=new Set(local.map(d=>d.condition_id));return [...local,...(currentCompiled()?.constraints||[]).filter(d=>!ids.has(d.condition_id))];}
 function classOverview(){
  const host=$('seq_class_counts');host.replaceChildren();const modern=structured(bundle,'sequence_constraints'),definitions=displayedDefinitions();
  for(const [key,label] of Object.entries(classes)){
   const count=definitions.filter(d=>d.condition_class===key).length,item=el('li');item.dataset.conditionClass=key;item.dataset.count=String(count);item.classList.toggle('has_conditions',count>0);
   const scoped=definitions.filter(d=>d.condition_class===key),active=scoped.filter(d=>conditionScope(d).group==='ACTIVE').length,uncertain=scoped.filter(d=>conditionScope(d).group==='UNCERTAIN').length,pending=scoped.filter(d=>conditionScope(d).group==='PENDING').length,inactive=scoped.length-active-uncertain-pending;Object.assign(item.dataset,{active:String(active),uncertain:String(uncertain),pending:String(pending),inactive:String(inactive)});item.classList.toggle('has_active_conditions',active>0);
   const heading=el('div');heading.append(el('strong',label),el('span',`총 ${count}개`));item.append(heading,el('p',`적용 중 ${active} · 미확인 ${uncertain} · 적용 안함 ${inactive}${pending?' · 계산 전 '+pending:''}`),el('p',classExamples[key]));host.append(item);
  }
  const unknown=definitions.filter(d=>!Object.hasOwn(classes,d.condition_class)).length;
  const excluded=modern?(original('sequence_constraints')?.new_definitions||[]).filter(d=>!bundle.new_definitions.some(n=>n.condition_id===d.condition_id)).length:0;
  $('seq_class_status').textContent=modern?`현재 제약 ${bundle.new_definitions.length}개 · 이전 장면에서 이어받은 정의 ${definitions.length-bundle.new_definitions.length}개 · 분류 미지정 ${unknown}개${excluded?' · 이 장면에서 제외 '+excluded+'개 (원본 보존)':''}`:bundle?.constraints.length?`기존 제약 ${definitions.length}개 · 분류 미지정 ${unknown}개${unknown?' · 분류 정보 없음: 각 제약에서 선택할 수 있습니다.':''}`:state.moment?.components.sequence_constraints?'생성된 제약이 없습니다. 이전 형식에는 분류 정보가 없습니다.':'제약 생성 전 · 생성하면 해당 분류와 항목 수가 표시됩니다.';
  if(view?.input_diagnostics?.[state.moment?.id]?.constraint_generation)$('seq_class_status').textContent='제약 재생성 필요 · 이전 생성 결과는 현재 제약에 포함하지 않습니다.';
 }
 const predicates={IN:'영역 안에 있음',OCCUPIES:'영역을 차지함',AHEAD_OF:'앞에 있음',BEHIND_OF:'뒤에 있음',LEFT_OF:'왼쪽에 있음',RIGHT_OF:'오른쪽에 있음',ADJACENT_TO:'옆에 있음',BOUNDARY_OF:'영역의 경계임',APPLIES_TO:'대상에 적용됨',PATH_CONFLICT:'진행 경로가 겹침',SIGNAL_RED:'빨간 신호',SIGNAL_GREEN:'초록 신호',PATH_CLEAR:'경로가 비어 있음',ZONE_CLOSED:'영역이 닫힘',STOPPED:'정지함',VISIBILITY_INSUFFICIENT:'시야가 부족함',SURFACE_RISK:'노면 위험이 있음',PASSAGE_COMPLETE:'통과가 끝남'};
 const evidence=()=>Object.fromEntries((state.moment?.frames||[]).map(f=>[f.frame_id,`영상 ${(f.timestamp_us/1e6).toFixed(3)}초`]));
 const contextEntities=()=>Object.values(Object.fromEntries([...(view?.input_diagnostics?.[state.moment?.id]?.inherited_entities||[]),...(data('sequence_constraints').original_sequence_context?.previous_entities||[]),...(data('sequence_coc').original_sequence_context?.previous_entities||[]),...(coc?.entities||[])].map(e=>[e.entity_id,e])));
 const refs=()=>Object.fromEntries(contextEntities().map(e=>[e.entity_id,e.description||kinds[e.kind]||'대상']));
 const lines=v=>Array.isArray(v)?v.join('\n'):v||'';
 function field(host,obj,key,label,path,options=null,{list=false,nullable=false,onChange=null}={}){
  const wrap=el('label');wrap.className='structured_field';wrap.append(el('span',label));
  const input=el(options?'select':list||key==='description'||key==='evidence_note'?'textarea':'input');input.dataset.path=path;input.setAttribute('aria-label',label);
  if(options){
   input.multiple=list;
   const choices={...(nullable?{'':'해당 없음 / 미확인'}:{}),...options};
   for(const v of list?(obj[key]||[]):[obj[key]])if(v!==null&&v!==undefined&&!(v in choices))choices[v]=key.endsWith('_ref')?refs()[v]||'대상 연결 확인 필요':v;
   for(const [value,text] of Object.entries(choices)){const o=el('option',text);o.value=value;o.selected=list?(obj[key]||[]).includes(value):value===String(obj[key]??'');if(key.endsWith('_ref')&&value&&!Object.hasOwn(options,value)){o.disabled=true;o.textContent=text+' · 종류 또는 연결 확인 필요';}input.append(o);}
  }else{input.value=key==='explanation_excerpt'?displayProse(obj[key]??''):list?lines(obj[key]):obj[key]??'';if(input.tagName==='TEXTAREA')input.rows=2;}
  const update=()=>{obj[key]=list?(options?[...input.selectedOptions].map(o=>o.value):input.value.split('\n').map(x=>x.trim()).filter(Boolean)):nullable&&!input.value?null:input.value;if(key==='explanation_excerpt'&&!coc.explanation.includes(obj[key])&&displayProse(coc.explanation).includes(obj[key]))editExplanation(displayProse(coc.explanation));if(onChange)onChange();save(host.closest('[data-component]')?.dataset.component||(host.closest('#seq_coc_fields')?'sequence_coc':'sequence_constraints')).catch(error);};
  input.addEventListener(options?'change':'input',update);if(path.startsWith('entities[')||['code','scope_state','truth','evidence_note','predicate','subject_ref','object_ref'].includes(key))input.addEventListener('change',()=>refreshForms());wrap.append(input);host.append(wrap);return input;
 }
 function section(host,title,note){const group=el('details');group.className='structured_group';group.dataset.group=(host.closest('.sequence_condition')?.dataset.conditionId||host.closest('#seq_coc_fields')?.id||'constraints')+':'+title.replace(/ · \d+개$/,'');group.append(el('summary',title));if(note)group.append(el('p',note));host.append(group);return group;}
 function row(host,title){const card=el('div');card.className='structured_row';if(title)card.append(el('h4',title));const grid=el('div');grid.className='structured_grid';card.append(grid);host.append(card);return grid;}
 function pointerFields(host,item,path){
  const grammar=view?.relation_grammar,r=grammar?.rules[item.predicate];
  const available=(allowed)=>Object.fromEntries(contextEntities().filter(e=>!allowed||allowed.includes(e.kind)).map(e=>[e.entity_id,refs()[e.entity_id]]));
  const p=field(host,item,'predicate','확인할 관계',path+'.predicate',predicates,{onChange:()=>{const next=grammar?.rules[item.predicate];if(next?.arity==='UNARY')item.object_ref=null;else if(next&&item.object_ref&&!Object.hasOwn(available(next.object_kinds),item.object_ref))item.object_ref=null;}});
  if(grammar){for(const [key,label] of Object.entries(grammar.groups)){const group=el('optgroup');group.label=label;for(const option of [...p.options])if(grammar.rules[option.value]?.group===key)group.append(option);p.append(group);}}
  field(host,item,'subject_ref','관찰 대상',path+'.subject_ref',available(r?.subject_kinds));
  if(r?.arity!=='UNARY')field(host,item,'object_ref','비교·적용 대상',path+'.object_ref',available(r?.object_kinds),{nullable:true});
  else if(item.object_ref){const note=el('p','이 항목은 한 대상의 상태입니다. 기존 입력에 불필요한 비교 대상이 연결되어 있습니다.');note.className='relation_format_notice';host.append(note);const clear=editButton('불필요한 비교 대상 연결 제거',async()=>{item.object_ref=null;const kind=host.closest('[data-component]')?.dataset.component||(host.closest('#seq_coc_fields')?'sequence_coc':'sequence_constraints');refreshForms();await save(kind);});host.append(clear);}
  if(r)host.append(el('small',`${grammar.groups[r.group]}${r.reference_frame?' · 현재 자차 진행 방향 기준':r.symmetric?' · 반대 방향도 같은 관계':r.arity==='UNARY'?' · 비교 대상 없음':''}`));
 }
 function originalDetails(host,value,id){const d=el('details');d.className='structured_original';d.dataset.group=id;d.append(el('summary','모델이 처음 제안한 내용 · 원문 보기'));const pre=el('pre',value?JSON.stringify(value,null,2):'아직 모델 제안이 없습니다.');if(id)pre.id=id;d.append(pre);if(value){const kind=id==='seq_coc_original'?'sequence_coc':'sequence_constraints',restore=editButton('모델 제안으로 되돌리기',async()=>{if(state.busy)return;if(kind==='sequence_coc')coc=project(value,kind);else bundle=project(value,kind);$('seq_accept_'+(kind==='sequence_coc'?'coc':'constraints')).checked=false;refreshForms();await save(kind);});restore.className='structured_edit';restore.dataset.restore=kind;d.append(restore);}host.append(d);}
 function cocSummary(){$('seq_explanation').value=displayProse(coc.explanation);$('seq_observations').textContent=displayProse(coc.observations||'관찰 사실 없음');$('seq_unknowns').textContent=displayProse(lines(coc.unknowns)||'미확인 내용 없음');$('seq_observed_actions').textContent='관찰 행동: '+(coc.observed_actions.map(a=>typeof a==='string'?names[a]||a:`${refs()[a.subject_ref]||'대상 연결 확인 필요'} · ${names[a.code]||a.code}${a.action_target_ref?' → '+(refs()[a.action_target_ref]||'대상 연결 확인 필요'):''}`).join(', ')||'확인되지 않음');}
 function refreshForms(path){
  const opened=new Set([...document.querySelectorAll('details[data-group][open]')].map(e=>e.dataset.group));const active=document.activeElement?.dataset.path;
  cocSummary();cocFields();cards();reviewEditor();for(const d of document.querySelectorAll('details[data-group]'))d.open=opened.has(d.dataset.group);
  if(path){const b=[...document.querySelectorAll('[data-add]')].find(e=>e.dataset.add===path);if(b?.closest('details'))b.closest('details').open=true;}
  const focus=[...document.querySelectorAll('#seq_review_editor [data-path],#seq_coc_fields [data-path],#seq_candidates [data-path]')].find(e=>e.dataset.path===active);if(focus)focus.focus({preventScroll:true});controls();
 }
 const currentEvidence=()=>state.moment?.frame?[state.moment.frame.frame_id]:[];
 const otherEntity=()=>(coc?.entities||[]).find(e=>e.entity_id!=='ego');
 const areaRefs=()=>Object.fromEntries(contextEntities().filter(e=>['ZONE','LANE'].includes(e.kind)).map(e=>[e.entity_id,refs()[e.entity_id]]));
 const area=()=>Object.keys(areaRefs())[0]||null;
 const atomDefault=()=>({predicate:otherEntity()?'PATH_CONFLICT':'STOPPED',subject_ref:otherEntity()?.entity_id||'ego',object_ref:otherEntity()?'ego':null});
 function editButton(text,fn){const b=el('button',text);b.onclick=()=>fn().catch(error);return b;}
 function addControl(host,path,items,limit,factory,kind){
  const b=editButton('항목 추가',async()=>{if(state.busy||items.length>=limit)return;items.push(factory());refreshForms(path);await save(kind);});b.className='structured_edit';b.dataset.add=path;b.dataset.full=String(items.length>=limit);b.setAttribute('aria-label',path+' 항목 추가');host.append(b);
 }
 function removeControl(host,path,items,index,kind,parent){
  const b=editButton('삭제',async()=>{if(state.busy)return;items.splice(index,1);refreshForms(parent);await save(kind);});b.className='structured_edit row_remove';b.dataset.remove=path;b.setAttribute('aria-label',path+' 삭제');host.append(b);
 }
 function entityDefault(){const used=new Set(coc.entities.map(e=>e.entity_id));const id=!used.has('ego')?'ego':Array.from({length:8},(_,i)=>'e'+(i+1)).find(x=>!used.has(x));return {entity_id:id,kind:id==='ego'?'EGO':'VEHICLE',description:id==='ego'?'자차':'추가한 대상',identity_status:'NEW_LOCAL',previous_entity_ref:null,evidence_refs:currentEvidence()};}


 function cocFields(){
  const host=$('seq_coc_fields');host.replaceChildren();host.hidden=!cocReviewPath;
  const close=editButton('수정창 닫기',async()=>{cocReviewPath=null;refreshForms();});close.dataset.closeCocReview='true';host.append(close);
  if(!structured(coc,'sequence_coc')){if(state.moment?.components.sequence_coc){host.append(el('p','영상·CAN에서 실제로 확인한 행동만 선택하세요. 주행 지속과 이미 정지한 상태 유지는 다릅니다.'));field(host,coc,'observed_actions','실제로 확인한 자차 행동 · 여러 선택 가능','observed_actions',names,{list:true});}return;}

  originalDetails(host,original('sequence_coc'),'seq_coc_original');
  const observations=section(host,'관찰과 근거','대상과 관계는 자동으로 채워집니다. 잘못 읽힌 부분만 고치세요.');
  field(observations,coc,'observations','보이는 사실','observations');field(observations,coc,'unknowns','아직 확인하지 못한 내용 · 한 줄에 하나','unknowns',null,{list:true});field(observations,coc,'evidence_refs','전체 관찰 근거','evidence_refs',evidence(),{list:true});
  const entities=section(host,'장면의 대상','예: 자차, 왼쪽 차량, 진입할 영역. 이전 대상과 같은지 함께 확인하세요.');
  coc.entities.forEach((e,i)=>{const h=row(entities,`대상 ${i+1}`),p=`entities[${i}]`;field(h,e,'kind','대상 종류',p+'.kind',kinds);field(h,e,'description','대상 설명',p+'.description');field(h,e,'identity_status','이전 장면과의 연결',p+'.identity_status',identities);field(h,e,'previous_entity_ref','이전 장면의 대상',p+'.previous_entity_ref',refs(),{nullable:true});field(h,e,'evidence_refs','대상을 확인한 근거',p+'.evidence_refs',evidence(),{list:true});removeControl(h.parentElement,p,coc.entities,i,'sequence_coc','entities');});
  addControl(entities,'entities',coc.entities,9,entityDefault,'sequence_coc');
  const relations=section(host,`대상 사이의 관계 · ${coc.relations.length}개`,'방향을 확인하세요. 예: 자차가 왼쪽 차량의 오른쪽에 있음. 두 대상을 바꾸면 뜻도 바뀝니다.');
  coc.relations.forEach((r,i)=>{const h=row(relations,`관계 ${i+1}`),p=`relations[${i}]`;pointerFields(h,r,p);field(h,r,'truth','현재 확인 상태',p+'.truth',truths);field(h,r,'evidence_refs','관계를 확인한 근거',p+'.evidence_refs',evidence(),{list:true});removeControl(h.parentElement,p,coc.relations,i,'sequence_coc','relations');});
  addControl(relations,'relations',coc.relations,8,()=>({...atomDefault(),truth:'UNKNOWN',evidence_refs:currentEvidence()}),'sequence_coc');
  const actions=section(host,`실제로 한 행동 · ${coc.observed_actions.length}개`,'예: 자차가 진입 영역으로 출발함. 행동 대상과 진행 경로를 따로 확인하세요.');
  coc.observed_actions.forEach((a,i)=>{const h=row(actions,`관찰 행동 ${i+1}`),p=`observed_actions[${i}]`;field(h,a,'code','행동',p+'.code',names);field(h,a,'subject_ref','행동한 대상',p+'.subject_ref',{ego:refs().ego||'자차'});field(h,a,'action_target_ref','행동이 향하는 대상 / 영역',p+'.action_target_ref',a.code==='ENTER'?areaRefs():refs(),{nullable:true});field(h,a,'movement_ref','진행 경로 / 영역',p+'.movement_ref',areaRefs(),{nullable:true});field(h,a,'evidence_refs','행동을 확인한 근거',p+'.evidence_refs',evidence(),{list:true});removeControl(h.parentElement,p,coc.observed_actions,i,'sequence_coc','observed_actions');});
  addControl(actions,'observed_actions',coc.observed_actions,5,()=>({code:'HOLD',subject_ref:'ego',action_target_ref:null,movement_ref:null,evidence_refs:currentEvidence()}),'sequence_coc');
  const complete=el('label'),checkbox=el('input');checkbox.type='checkbox';checkbox.dataset.path='action_observation_complete';checkbox.checked=coc.action_observation_complete===true;
  checkbox.onchange=()=>{coc.action_observation_complete=checkbox.checked;save('sequence_coc').catch(error);};complete.append(checkbox,document.createTextNode(' 목록 밖 행동도 하지 않았음을 영상에서 확인했습니다'));actions.append(complete);
  const reasons=section(host,'설명과 행동을 연결한 이유','모델이 설명의 어느 부분으로 어떤 행동을 설명했는지 보여줍니다. 틀린 이유만 고치세요.');
  if(!coc.reason_bindings?.length)reasons.append(el('p','연결된 이유가 없습니다. 과거 문장에서 자동으로 추측하지 않습니다.'));
  (coc.reason_bindings||[]).forEach((b,i)=>{const h=row(reasons,`이유 ${i+1}`),p=`reason_bindings[${i}]`;
   const select=el('select');select.dataset.path=p+'.action_index';select.setAttribute('aria-label','설명할 실제 행동');coc.observed_actions.forEach((a,j)=>{const o=el('option',`행동 ${j+1} · ${names[a.code]}`);o.value=String(j);o.selected=j===b.action_index;select.append(o);});select.onchange=()=>{b.action_index=Number(select.value);save('sequence_coc').catch(error);};h.append(select);
   field(h,b,'explanation_excerpt','연결된 설명 원문',p+'.explanation_excerpt');
   (b.reasons||[]).forEach((g,j)=>{const r=row(reasons,`확인할 이유 ${j+1}`),gp=p+`.reasons[${j}]`;pointerFields(r,g.atom,gp+'.atom');field(r,g,'expected_truth','이유가 성립하는 상태',gp+'.expected_truth',{TRUE:'사실임',FALSE:'사실이 아님'});removeControl(r.parentElement,gp,b.reasons,j,'sequence_coc',p+'.reasons');});
   addControl(reasons,p+'.reasons',b.reasons,8,()=>({atom:atomDefault(),expected_truth:'TRUE'}),'sequence_coc');removeControl(h.parentElement,p,coc.reason_bindings,i,'sequence_coc','reason_bindings');
  });
  const addReason=editButton('이유 연결 추가',async()=>{if(!coc.observed_actions.length)return;coc.reason_bindings??=[];if(coc.reason_bindings.length>=5)return;coc.reason_bindings.push({action_index:0,explanation_excerpt:coc.explanation,reasons:[]});refreshForms();await save('sequence_coc');});addReason.className='structured_edit';addReason.dataset.full=String(!coc.observed_actions.length||(coc.reason_bindings?.length||0)>=5);reasons.append(addReason);
  if(cocReviewPath)for(const child of host.children){if(child===close)continue;const paths=[...child.querySelectorAll('[data-path]')].map(e=>e.dataset.path);child.hidden=!paths.some(p=>p===cocReviewPath||p.startsWith(cocReviewPath+'.')||p.startsWith(cocReviewPath+'['));}
 }
 function cards(){
  classOverview();
  const generationGap=view?.input_diagnostics?.[state.moment?.id]?.constraint_generation;
  if(generationGap){const host=$('seq_candidates');host.replaceChildren();const notice=el('div');notice.className='constraint_format_notice';notice.dataset.generationGap='true';notice.append(el('strong','현재 CoC로 제약을 새로 생성하세요.'),el('p',generationGap));host.append(notice);const history=el('details');history.append(el('summary','이전 제약 · 읽기 전용 이력'),el('pre',JSON.stringify(bundle,null,2)));host.append(history);return;}
  if(!structured(bundle,'sequence_constraints'))return legacyCards();
  const host=$('seq_candidates');host.replaceChildren();originalDetails(host,original('sequence_constraints'),'seq_constraints_original');
  if(!entityCocReady()){const note=el('p','현재 CoC에는 장면 대상 정보가 없습니다. 이 입력으로 만든 제약은 적용 대상을 확인할 수 없습니다. 1단계에서 CoC를 다시 생성·검토한 뒤 제약을 다시 생성하세요.');note.className='constraint_format_notice';note.setAttribute('role','status');host.append(note);}
  const bindingGap=view?.input_diagnostics?.[state.moment?.id]?.constraint_binding;
  if(bindingGap){const notice=el('div');notice.className='constraint_format_notice';notice.dataset.bindingGap='true';notice.append(el('strong','이전 제약의 대상 연결을 재사용할 수 없습니다.'),el('p',bindingGap));const prepare=editButton('현재 CoC로 제약 재생성 준비',async()=>{showStage(2);$('seq_reset_constraints').click();});notice.append(prepare);host.append(notice);}
  const definitionsToShow=displayedDefinitions(),groups=scopeGroups(host,definitionsToShow);
  if(!bundle.new_definitions.length){const note=el('p',entityCocReady()?'새로 제안된 제약은 0개입니다. 관찰 항목 수와 제약 수는 다릅니다. 이전 조건과 미확인 내용을 검토하세요. 제약 0개만으로 안전이나 검증 통과를 뜻하지 않습니다.':'제약 후보는 0개이지만, CoC의 대상 정보가 부족하여 이 장면에 제약이 필요 없다고 판단할 수 없습니다.');note.className='constraint_empty_notice';host.append(note);}
  bundle.new_definitions.forEach((d,i)=>{
   const card=el('div');card.className='sequence_condition';card.dataset.conditionId=d.condition_id;card.append(el('h3',`제약 ${i+1}`));scopeBadge(card,d);groups[conditionScope(d).group].append(card);const p=`new_definitions[${i}]`,orig=original('sequence_constraints')?.new_definitions?.find(x=>x.condition_id===d.condition_id);
   const classification=el('div');classification.className='constraint_class_field';card.append(classification);field(classification,d,'condition_class','제약 분류',p+'.condition_class',{'':'분류 미지정',...classes},{nullable:true});
   const pair=el('div');pair.className='seq_pair';pair.append(el('pre',orig?.description||'모델 설명 없음'));const editable=el('div');pair.append(editable);card.append(pair);field(editable,d,'description','검토할 조건 설명',p+'.description');
   const summary=el('p',`관련 행동: ${d.actions.map(a=>names[a]||a).join(', ')} · ${effects[d.effect]||d.effect}`);summary.className='constraint_brief';card.append(summary);
   const target=d.action_target_ref&&refs()[d.action_target_ref];card.append(el('p',target?'대상: '+target:'적용 대상이 아직 연결되지 않았습니다. 검증 전에 대상 확인이 필요합니다.'));
   removeControl(card,p,bundle.new_definitions,i,'sequence_constraints','new_definitions');
   const remove=card.querySelector('[data-remove]');remove.textContent='이 장면에서 제외';remove.setAttribute('aria-label',`제약 ${i+1} 이 장면에서 제외`);

  });
  for(const d of definitionsToShow.filter(d=>!bundle.new_definitions.some(n=>n.condition_id===d.condition_id))){const card=el('div');card.className='sequence_condition carried_condition';card.dataset.conditionId=d.condition_id;card.append(el('h3','이전 장면에서 이어받은 조건'),el('p',classes[d.condition_class]||'분류 미지정'),el('p',d.description));scopeBadge(card,d);card.append(el('p','이 정의는 이전 장면에 있습니다. 현재 사실을 수정해 유지·해제 여부를 다시 검사하세요.'));const src=Object.values(currentCompiled()?.source_map||{}).find(s=>s.value?.condition_id===d.condition_id);if(src)card.append(editButton('조건 원문으로 이동',()=>openSource(src)));groups[conditionScope(d).group].append(card);}
  const facts=section(host,`관찰 항목 · ${bundle.facts.length}개 (미확인 포함)`,'대상 수가 아니라 정지 여부·시야·노면 등 확인한 항목 수입니다. 관찰만으로 제약이 자동 확정되지는 않습니다. 미확인은 조건이 사라졌다는 뜻이 아닙니다.');
  if(!bundle.facts.length)facts.append(el('p','제안한 관찰 사실이 없습니다.'));else{const preview=el('ul');preview.className='fact_preview';for(const f of bundle.facts){const a=f.atom,label=a.subject_ref==='ego'?'자차':refs()[a.subject_ref]||'대상 연결 필요',object=a.object_ref?(a.object_ref==='ego'?'자차':refs()[a.object_ref]||'대상 연결 필요'):null;const targetMissing=['PATH_CLEAR','ZONE_CLOSED'].includes(a.predicate)&&!contextEntities().some(e=>e.entity_id===a.subject_ref&&['LANE','ZONE'].includes(e.kind));preview.append(el('li',`${label}${object?' → '+object:''}: ${predicates[a.predicate]||a.predicate} — ${targetMissing?'대상 연결 필요':({TRUE:'해당함',FALSE:'해당하지 않음',UNKNOWN:'아직 확인 못함',CONFLICT:'근거가 서로 다름'})[f.truth]||f.truth}`));}host.insertBefore(preview,facts);}
  bundle.facts.forEach((f,i)=>{const h=row(facts,`관찰 사실 ${i+1}`),p=`facts[${i}]`;pointerFields(h,f.atom,p+'.atom');field(h,f,'truth','현재 확인 상태',p+'.truth',truths);field(h,f,'evidence_refs','관찰 근거',p+'.evidence_refs',evidence(),{list:true});field(h,f,'evidence_note','근거 설명',p+'.evidence_note');removeControl(h.parentElement,p,bundle.facts,i,'sequence_constraints','facts');});
  addControl(facts,'facts',bundle.facts,24,()=>({atom:atomDefault(),truth:'UNKNOWN',evidence_refs:currentEvidence(),evidence_note:'현재 영상에서 확인할 사실'}),'sequence_constraints');
  const unknowns=section(host,'이전 조건과 미확인 내용');field(unknowns,bundle,'unresolved_previous_condition_refs','아직 확인하지 못한 이전 조건 · 한 줄에 하나','unresolved_previous_condition_refs',null,{list:true});field(unknowns,bundle,'unknowns','미확인 내용 · 한 줄에 하나','unknowns',null,{list:true});
 }
 async function openSource(source){
  if(!state.moment||state.busy)return;
  if(source.moment_id&&source.moment_id!==state.moment.id)await loadMoment(source.moment_id);
  showStage(source.component==='sequence_coc'?1:2);
  let path=Array.isArray(source.path)?source.path.reduce((s,k)=>typeof k==='number'?s+`[${k}]`:s?(s+'.'+k):k,''):String(source.path||'');
  if(path.startsWith('/'))path=path.slice(1).split('/').map(x=>x.replace(/~1/g,'/').replace(/~0/g,'~')).reduce((s,k)=>/^\d+$/.test(k)?s+`[${k}]`:s?s+'.'+k:k,'');
  if(source.component==='sequence_coc'){cocReviewPath=path&&path!=='explanation'?path:null;cocFields();controls();}
  const fields=[...document.querySelectorAll('[data-path]')];if(/^facts\[\d+\]$/.test(path)&&source.value?.truth)path+='.truth';let target=fields.find(e=>e.dataset.path===path)||fields.find(e=>e.dataset.path.startsWith(path+'.')||e.dataset.path.startsWith(path+'['));
  if(!target&&source.component==='sequence_coc'&&path==='explanation')target=$('seq_explanation');
  if(!target&&source.component==='sequence_constraints'&&path.startsWith('new_definitions[')){const cid=source.value?.condition_id,card=[...document.querySelectorAll('.sequence_condition')].find(e=>cid?e.dataset.conditionId===cid:e.querySelector(`[data-path="${path.match(/^new_definitions\[\d+\]/)?.[0]}.description"]`));target=card?.querySelector('[data-path$=".description"]');}
  target=target||$(source.component==='sequence_coc'?'seq_coc_fields':'seq_candidates');
  for(const x of document.querySelectorAll('.review_highlight'))x.classList.remove('review_highlight');
  if(target){for(let a=target.parentElement;a;a=a.parentElement)if(a.tagName==='DETAILS')a.open=true;target.classList.add('review_highlight');target.scrollIntoView({behavior:'smooth',block:'center'});target.focus({preventScroll:true});}
 }
 function reviewLocation(source){
  const path=Array.isArray(source.path)?'/'+source.path.join('/'):String(source.path||''),group=path.match(/\/(constraints|new_definitions|facts|relations|entities|observed_actions)\/(\d+)/);
  const names={constraints:'제약',new_definitions:'제약',facts:'관찰 사실',relations:'대상 관계',entities:'장면 대상',observed_actions:'실제 행동'},fields={scope_state:'적용 상황',truth:'확인 상태',evidence_note:'관찰 근거',explanation:'CoC 설명',observed_actions:'실제 행동',description:'설명'};
  const label=fields[path.split('/').at(-1)];return group?`${names[group[1]]} ${Number(group[2])+1}${label?' · '+label:''}`:label||'연결된 관찰·제약';
 }
 function readableStatement(value,labels={}){
  const ref=id=>labels[id]||(coc?.entities||[]).find(e=>e.entity_id===id)?.description||'대상 미확인';
  if(Array.isArray(value))return value.map(v=>readableStatement(v,labels)).join(', ');
  if(!value||typeof value!=='object')return typeof value==='string'?(names[value]||value):'입력 확인 필요';
  if(value.description)return value.description;
  if(value.explanation_excerpt)return value.explanation_excerpt;
  const a=value.atom||value;
  if(a.predicate){const subject=ref(a.subject_ref),object=ref(a.object_ref),phrases={ZONE_CLOSED:`‘${subject}’의 통행이 막혀 있는지 확인하는 항목입니다.`,APPLIES_TO:`‘${subject}’의 ‘${object}’에 대한 적용 여부가 입력되어 있습니다.`,IN:`${subject}가 ${object} 안에 있는지 확인하는 항목입니다.`,PATH_CONFLICT:`${subject}와 ${object}의 진행 경로가 겹치는지 확인하는 항목입니다.`,PASSAGE_COMPLETE:`${subject}가 ${object}을 완전히 지나쳤는지 확인하는 항목입니다.`};return phrases[a.predicate]||`${subject}${a.object_ref?'와 '+object+'의 관계':''}: ${predicates[a.predicate]||a.predicate}`;}
  if(value.code)return `${ref(value.subject_ref)}의 관찰 행동: ${names[value.code]||value.code}${value.action_target_ref?' · '+ref(value.action_target_ref):''}`;
  return '연결된 입력을 확인하세요.';
 }
 function sourcePath(source){
  const parts=Array.isArray(source.path)?source.path:String(source.path||'').replace(/^\//,'').split('/').map(x=>x.replace(/~1/g,'/').replace(/~0/g,'~'));
  return parts.reduce((s,k)=>/^\d+$/.test(String(k))?s+`[${k}]`:s?s+'.'+k:k,'');
 }
 async function openReviewSource(source,reviewMomentId){
  if(!state.moment||state.busy)return;
  const returnId=reviewMomentId||source.review_moment_id||editorSource?.review_moment_id||state.moment.id;
  await flush();if(source.moment_id&&source.moment_id!==state.moment.id){await loadMoment(source.moment_id);await render();}
  editorSource={...clone(source),review_moment_id:returnId};if(source.batch)beginReviewDraft();showStage(4);reviewEditor();controls();
  const path=sourcePath(source)+(source.suggestion?'.'+source.suggestion.field:''),fields=[...$('seq_review_editor').querySelectorAll('[data-path]')];
  const target=fields.find(e=>e.dataset.path===path)||fields.find(e=>e.dataset.path===path+'.truth')||fields[0];
  $('seq_review_editor').scrollIntoView({block:source.observation_context?'start':'center'});target?.focus({preventScroll:true});
 }
 async function applyReviewSuggestion(source,suggestion){
  if(state.busy)return;
  await openReviewSource({...source,suggestion});
  const path=sourcePath(source),match=path.match(/^(\w+)\[(\d+)\]/),root=source.component==='sequence_coc'?coc:bundle,item=match?root?.[match[1]]?.[Number(match[2])]:null;
  if(!item||canonical(item)!==canonical(source.value))throw new Error('검사 이후 입력이 바뀌어 이 제안을 반영할 수 없습니다. 최신 입력을 직접 편집하거나 다시 검증하세요.');
  item[suggestion.field]=suggestion.value;refreshForms();await save(source.component);await flush();
  if(editorSource?.moment_id===source.moment_id&&editorSource.path===source.path){editorSource.correctionApplied=true;reviewEditor();controls();}
 }
 function observationSource(atom){
  for(const [component,key,values] of [['sequence_constraints','facts',bundle?.facts],['sequence_coc','relations',coc?.relations]]){
   const index=values?.findIndex(v=>canonical(v.atom||{predicate:v.predicate,subject_ref:v.subject_ref,object_ref:v.object_ref})===canonical(atom));
   if(index>=0)return {moment_id:state.moment.id,component,path:`/${key}/${index}`,value:clone(values[index])};
  }
  return null;
 }
 function lifecycleReview(item,momentId){
  if(!['EVIDENCE_MISSING','LIFECYCLE_CONFLICT'].includes(item.code)||momentId!==state.moment?.id)return null;
  const scene=view?.stages?.verification?.result?.scenes.find(s=>s.moment_id===momentId),rows=[];
  for(const source of item.sources||[]){const d=source.value,phase=scene?.states?.[d?.condition_id];if(!phase||!d.activation_all_of)continue;
   for(const [key,label,status] of [['activation_all_of','조건 시작',phase.activation_guard],['release_any_of','조건 해제',phase.release_guard]]){
    for(const guard of d[key]){const linked=(item.sources||[]).filter(s=>{const a=s.value?.atom||s.value;return s.moment_id===momentId&&a?.predicate&&canonical({predicate:a.predicate,subject_ref:a.subject_ref,object_ref:a.object_ref})===canonical(guard.atom);});
     for(const observation of linked.length?linked:[observationSource(guard.atom)]){const v=observation?.value;
      rows.push({label,status,expected:guard.expected_truth,atom:guard.atom,observation,definition:d.description,condition_id:d.condition_id,labels:{...source.entity_labels,...observation?.entity_labels},
       missing:!v,needsInput:status==='UNKNOWN'&&(!v||v.truth==='UNKNOWN'||!v.evidence_refs?.includes(state.moment.frame.frame_id)||observation.component==='sequence_constraints'&&!v.evidence_note?.trim())});
     }
    }
   }
  }
  const unique=[...new Map(rows.map(r=>[canonical([r.condition_id,r.label,r.atom,r.expected,r.observation?.component,r.observation?.path]),r])).values()];
  return unique.length?{rows:unique,pending:unique.filter(r=>r.needsInput),conflict:item.code==='LIFECYCLE_CONFLICT',actionCheck:scene.properties?.results?.find(p=>p.property_id==='B6')?.status}:null;
 }
 function observationInputs(lifecycle){
  const inputs=new Map();
  for(const r of lifecycle?.pending||[]){const key=canonical(r.atom);if(!inputs.has(key))inputs.set(key,{...r,contexts:[]});const input=inputs.get(key);
   const context={description:r.definition,label:r.label,expected:r.expected};if(!input.contexts.some(c=>canonical(c)===canonical(context)))input.contexts.push(context);
  }
  return [...inputs.values()];
 }
 const observationButtonLabel=r=>({ZONE_CLOSED:'통행 차단 여부 입력',PASSAGE_COMPLETE:'통과 여부 입력'})[r.atom.predicate]||`${r.label} 관찰 입력`;
 async function openObservationInput(atom,batch=false,context=null){
  if(state.busy)return;await flush();
  const existing=observationSource(atom);if(existing){const source={...existing,observation_context:context};await (batch?openBatchSource(source):openReviewSource(source));return;}
  if(batch)beginReviewDraft();
  editorSource={moment_id:state.moment.id,component:'sequence_constraints',batch,path:'/facts',observation_context:context,observationDraft:{atom:clone(atom),truth:'',evidence_note:'',evidence_refs:[]}};
  showStage(4);reviewEditor();controls();$('seq_review_editor').scrollIntoView({block:context?'start':'center'});$('seq_review_editor').querySelector('select')?.focus({preventScroll:true});
 }
 function postconditionReview(item,momentId){
  if(item.code!=='POSTCONDITION_UNKNOWN'||momentId!==state.moment?.id)return null;
  const rows=[];
  for(const source of item.sources||[])for(const guard of source.value?.expected_postconditions||[]){const observation=observationSource(guard.atom),v=observation?.value;
   const needsInput=!v||v.truth==='UNKNOWN'||!v.evidence_refs?.includes(state.moment.frame.frame_id)||observation.component==='sequence_constraints'&&!v.evidence_note?.trim();
   rows.push({label:'기대 결과',definition:source.value.description,expected:guard.expected_truth,status:needsInput?'UNKNOWN':v.truth===guard.expected_truth?'TRUE':'FALSE',atom:guard.atom,observation,labels:source.entity_labels,missing:!v,needsInput});
  }
  return rows.length?{rows,pending:rows.filter(r=>r.needsInput),expectation:true}:null;
 }
 function observationEditor(host){
  const draft=editorSource.observationDraft,passage=draft.atom.predicate==='PASSAGE_COMPLETE';
  host.append(el('h4',passage?'통과 여부 입력':'누락된 관찰 사실 입력'));if(!editorSource.observation_context)host.append(el('p',readableStatement(draft,refs())));host.append(el('p','조건의 정의는 그대로 두고 현재 영상에서 확인한 사실을 추가합니다. 선택을 저장하기 전에는 입력을 변경하지 않습니다.'));
  const input=(tag,label)=>{const wrap=el('label');wrap.className='structured_field';wrap.append(el('span',label));const e=el(tag);e.setAttribute('aria-label',label);wrap.append(e);host.append(wrap);return e;};
  const truth=input('select','현재 확인 상태');truth.dataset.observationTruth='true';
  const choices=passage?{'':'선택하세요',TRUE:'이미 완전히 지나쳤음',FALSE:'아직 완전히 지나치지 않았음',UNKNOWN:'영상으로 판단할 수 없음'}:{'':'선택하세요',TRUE:truths.TRUE,FALSE:truths.FALSE,UNKNOWN:truths.UNKNOWN};
  for(const [value,label] of Object.entries(choices)){const o=el('option',label);o.value=value;o.selected=value===draft.truth;truth.append(o);}truth.onchange=()=>{draft.truth=truth.value;};
  const note=input('textarea','영상에서 확인한 근거 또는 판단하기 어려운 이유');note.dataset.observationNote='true';note.rows=3;note.value=draft.evidence_note;note.oninput=()=>{draft.evidence_note=note.value;};
  const frames=input('select','판단에 사용한 영상');frames.dataset.observationEvidence='true';frames.multiple=true;
  for(const f of [...(state.moment.frames||[])].sort((a,b)=>b.timestamp_us-a.timestamp_us)){const o=el('option',`${f.timestamp_us===state.moment.t0_us?'현재':'이전'} 영상 · ${(f.timestamp_us/1e6).toFixed(3)}초`);o.value=f.frame_id;o.selected=draft.evidence_refs.includes(f.frame_id);frames.append(o);}frames.onchange=()=>{draft.evidence_refs=[...frames.selectedOptions].map(o=>o.value);};
  host.append(el('p','해당함·해당하지 않음으로 확정하려면 현재 영상과 근거 설명이 필요합니다. 판단할 수 없음으로 저장하면 제약은 해제되지 않으며 확인 필요가 남을 수 있습니다.'));
  const validation=el('p');validation.setAttribute('role','alert');host.append(validation);
  const saveObservation=editButton(reviewDraft?'수정 초안에 추가':'관찰 사실 저장',async()=>{
   if(state.busy)return;
   if(!draft.truth||!draft.evidence_note.trim()||draft.truth!=='UNKNOWN'&&!draft.evidence_refs.includes(state.moment.frame.frame_id)){validation.textContent='확인 상태와 근거 설명을 입력하세요. 사실을 확정하려면 현재 영상을 선택하세요.';return;}
   const existing=observationSource(draft.atom);if(existing){await openReviewSource(existing);return;}
   if(bundle.facts.length>=24){validation.textContent='관찰 사실 입력 한도에 도달했습니다. 기존 항목을 검토하세요.';return;}
   const index=bundle.facts.length,value=clone(draft);bundle.facts.push(value);editorSource={moment_id:state.moment.id,component:'sequence_constraints',batch:!!reviewDraft,path:`/facts/${index}`,value,observation_context:editorSource.observation_context};
   await save('sequence_constraints');await flush();reviewEditor();controls();
  });saveObservation.className='structured_edit';saveObservation.dataset.saveObservation='true';host.append(saveObservation);
 }
 function reviewEditor(){
  if(editorSource?.component==='sequence_constraints'&&view?.input_diagnostics?.[state.moment?.id]?.constraint_generation)editorSource=null;
  const host=$('seq_review_editor');host.replaceChildren();host.hidden=!editorSource;if(!editorSource)return;
  host.dataset.component=editorSource.component;host.append(el('h3',`시점 ${state.moment.ordinal+1} · ${editorSource.component==='sequence_coc'?'CoC':'제약'} · ${reviewLocation(editorSource)} 수정`),el('p',reviewDraft?'다른 문제도 이어서 수정할 수 있습니다. 아래 수정 반영을 누르기 전에는 저장본을 바꾸지 않습니다.':'개별 수정: 입력은 즉시 저장됩니다. 검토 완료 후 다시 검증하세요.'));
  if(editorSource.review_moment_id&&editorSource.review_moment_id!==state.moment.id){const returnId=editorSource.review_moment_id,ordinal=state.moments.find(m=>m.id===returnId)?.ordinal;host.append(el('p',`이전 시점의 제약 정의를 수정하고 있습니다. 검토 완료 후 시점 ${ordinal+1}로 돌아가 현재 관찰과 함께 다시 검증하세요.`));const back=editButton(`시점 ${ordinal+1} 검증으로 돌아가기`,async()=>{await flush();await loadMoment(returnId);await render();showStage(4);});back.dataset.reviewReturn=returnId;host.append(back);}
  host.append(editButton('수정창 닫기',async()=>{editorSource=null;if(reviewDraft&&!draftChanged()){sessionStorage.removeItem(draftKey());reviewDraft=null;}reviewEditor();controls();}));
  if(editorSource.observation_context){const context=editorSource.observation_context,box=el('div');box.className='review_input_origin';box.dataset.observationContext='true';
   const descriptions=[...new Set(context.contexts.map(c=>c.description).filter(Boolean))];box.append(el('strong','관련 제약'));for(const description of descriptions)box.append(el('blockquote',description));
   box.append(el('strong','확인할 사실'),el('p',readableStatement(context.atom,{...refs(),...context.labels})));
   for(const c of context.contexts)box.append(el('p',`${c.label}에서 요구하는 상태: ${context.atom.predicate==='PASSAGE_COMPLETE'?(c.expected==='TRUE'?'이미 완전히 지나쳤음':'아직 완전히 지나치지 않았음'):context.atom.predicate==='ZONE_CLOSED'?(c.expected==='TRUE'?'통행이 막혀 있음':'통행이 막혀 있지 않음'):truths[c.expected]}`));
   box.append(el('p','위 상태는 제약의 기준입니다. 아래 확인 상태는 현재 영상에서 실제 확인한 값으로 선택하세요.'));host.append(box);
  }
  if(editorSource.observationDraft){observationEditor(host);return;}
  const root=editorSource.component==='sequence_coc'?coc:bundle,path=sourcePath(editorSource),match=path.match(/^(\w+)\[(\d+)\]/),key=match?.[1],index=match?Number(match[2]):null,item=match?root?.[key]?.[index]:null;
  const suggestion=editorSource.suggestion;
  if(suggestion){
   const box=el('div');box.className='repair_suggestion';box.append(el('h4',suggestion.kind==='COUNTEREXAMPLE_CANDIDATE'?'반례 기반 수정 후보':'근거 문장에 따른 수정 후보'));
   const labels=suggestion.field==='code'?names:truths;box.append(el('p',`현재: ${labels[suggestion.before]||suggestion.before} → 후보: ${labels[suggestion.value]||suggestion.value}`),el('p','제안 근거: '+suggestion.basis),el('p',suggestion.message));
   const outdated=!item||canonical(item)!==canonical(editorSource.value);if(editorSource.correctionApplied)box.append(el('p',reviewDraft?'제안을 수정 초안에 넣었습니다. 수정 반영을 눌러 저장하세요.':'수정 제안을 승인하여 입력에 반영했습니다. 검토 완료 후 EBLC를 생성하고 다시 검증하세요.'));else if(outdated)box.append(el('p','검사 당시 입력과 현재 입력이 다릅니다. 후보를 자동 반영하지 않습니다. 다시 검증하거나 직접 수정하세요.'));
   const apply=editButton(reviewDraft?'제안을 초안에 넣기':'수정 제안 승인·반영',()=>applyReviewSuggestion(editorSource,suggestion));apply.dataset.full=String(outdated);apply.disabled=outdated;box.append(apply);host.append(box);
  }
  const plainRefs={...refs(),...editorSource.entity_labels,...editorSource.observation_context?.labels};
  if(match&&!item){host.append(el('p','이 항목은 현재 입력에서 삭제되었거나 위치가 바뀌었습니다. 현재 입력으로 다시 검증하세요.'));return;}
  if(match&&editorSource.value&&canonical(item)!==canonical(editorSource.value)&&!path.includes('.'))host.append(el('p','검사 당시 원문과 현재 입력이 다릅니다. 최신 입력을 기준으로 검토하세요.'));
  if(item&&(key==='facts'||key==='relations')){
   const a=item.atom||item,p=key+'['+index+']',ap=p+(item.atom?'.atom':'');
   const structure=el('details');structure.append(el('summary','대상·관계 수정'));structure.open=!!editorSource.formatError;const grid=row(structure);pointerFields(grid,a,ap);if(!editorSource.observation_context)host.append(el('p',readableStatement(item,plainRefs)));field(host,item,'truth','현재 확인 상태',p+'.truth',a.predicate==='PASSAGE_COMPLETE'?{TRUE:'이미 완전히 지나쳤음',FALSE:'아직 완전히 지나치지 않았음',UNKNOWN:'영상으로 판단할 수 없음',CONFLICT:'근거 충돌'}:truths);host.append(structure);
   if(a.predicate==='APPLIES_TO')host.append(el('p','신호 → 자차·차로·영역만 지원합니다. 교통 표지는 아직 지원하지 않습니다. 판단할 수 없음으로 바꾸어도 잘못된 대상 종류는 해결되지 않습니다.'));
   if(key==='facts')field(host,item,'evidence_note','영상·CAN에서 확인한 근거',p+'.evidence_note');
  }else if(item&&key==='observed_actions'){
   const grid=row(host),p=key+'['+index+']';field(grid,item,'code','실제로 한 행동',p+'.code',names);field(grid,item,'subject_ref','행동 주체',p+'.subject_ref',plainRefs);field(grid,item,'action_target_ref','행동 대상',p+'.action_target_ref',plainRefs,{nullable:true});field(grid,item,'movement_ref','진행 경로',p+'.movement_ref',areaRefs(),{nullable:true});
  }else if(item&&key==='entities'){
   const p=key+'['+index+']';field(host,item,'description','대상 설명',p+'.description');field(host,item,'kind','대상 종류',p+'.kind',kinds);
  }else if(item&&key==='reason_bindings'){
   host.append(el('p',item.explanation_excerpt));
   item.reasons.forEach((g,j)=>{const grid=row(host,`설명에 연결된 이유 ${j+1}`),p=`reason_bindings[${index}].reasons[${j}]`;pointerFields(grid,g.atom,p+'.atom');field(grid,g,'expected_truth','이유가 성립하는 상태',p+'.expected_truth',{TRUE:'사실임',FALSE:'사실이 아님'});});
  }else if(item&&(key==='new_definitions'||key==='constraints')){
   const p=key+'['+index+']';field(host,item,'description','제약 설명',p+'.description');field(host,item,'condition_class','제약 분류',p+'.condition_class',classes,{nullable:true});
   if(key==='constraints'){field(host,item,'scope_state','현재 적용 상황',p+'.scope_state',{IN_SCOPE:'적용 중',ENDED:'적용 상황이 끝남',UNKNOWN:'판단할 수 없음'});field(host,item,'truth','현재 확인 상태',p+'.truth',truths);field(host,item,'evidence_note','영상·CAN에서 확인한 근거',p+'.evidence_note');}
   else{
    host.append(el('p','설명을 바꾸는 것만으로 실행 조건은 바뀌지 않습니다. 영상 근거에 맞는 행동·조건을 아래에서 수정하세요.'));
    const grid=row(host);field(grid,item,'effect','이 조건이 성립할 때',p+'.effect',effects);field(grid,item,'actions','관련 행동 · 여러 선택 가능',p+'.actions',names,{list:true});field(grid,item,'action_target_ref','행동 대상',p+'.action_target_ref',plainRefs,{nullable:true});field(grid,item,'movement_ref','진행 경로',p+'.movement_ref',areaRefs(),{nullable:true});
    for(const [k,label] of [['activation_all_of','조건 시작 · 모두 성립'],['release_any_of','조건 해제 · 하나 이상 성립'],['preconditions','행동 전에 확인할 사실'],['expected_postconditions','행동 뒤에 기대하는 사실']]){
     if(!item[k]?.length)continue;const group=section(host,label);group.open=!!editorSource.formatError;
     item[k].forEach((g,j)=>{const grid=row(group,`조건 ${j+1}`),gp=p+`.${k}[${j}]`;pointerFields(grid,g.atom,gp+'.atom');field(grid,g,'expected_truth','필요한 확인 상태',gp+'.expected_truth',{TRUE:'해당함',FALSE:'해당하지 않음'});});
    }
    if(editorSource.lifecycleConflict){const passed=item.release_any_of.find(g=>g.atom.predicate==='PASSAGE_COMPLETE'&&g.expected_truth==='TRUE');
     if(passed&&!item.activation_all_of.some(g=>canonical(g.atom)===canonical(passed.atom)&&g.expected_truth==='FALSE')){
      host.append(el('p','두 관찰이 모두 맞다면, 이 제약을 완전히 통과하기 전까지만 적용하려는 것인지 확인하세요. 아래 버튼은 시작 조건에 통과 완료가 아님을 추가합니다. 관찰값은 바꾸지 않으며 검토 완료와 재검증이 필요합니다.'));
      const narrow=editButton('시작 조건에 완전 통과 전을 추가',async()=>{item.activation_all_of.push({atom:clone(passed.atom),expected_truth:'FALSE'});await save('sequence_constraints');await flush();reviewEditor();controls();});narrow.dataset.refineLifecycle='PASSAGE_COMPLETE';host.append(narrow);
     }
    }
    if(item.expected_postconditions?.length){field(host,item,'postcondition_window','기대 결과 확인 시점',p+'.postcondition_window',{UNSPECIFIED:'아직 정하지 않음',NEXT_OBSERVATION:'바로 다음 시점'});host.append(el('p','바로 다음 시점은 이 제약의 행동을 실제 수행한 뒤의 영상입니다. 수행하지 않은 행동은 결과 검사 대상이 되지 않습니다. 확인 시점만 지정해도 실제 결과 관찰이 없으면 미확인으로 남습니다.'));}
   }
  }else if(path==='observed_actions'&&!structured(coc,'sequence_coc'))field(host,coc,'observed_actions','실제로 확인한 자차 행동 · 여러 선택 가능',path,names,{list:true});
  else if(path==='observed_actions'&&structured(coc,'sequence_coc'))addControl(host,path,coc.observed_actions,8,()=>({code:'CONTINUE',subject_ref:'ego',action_target_ref:null,movement_ref:null,evidence_refs:currentEvidence()}),'sequence_coc');
  else if(path==='explanation')field(host,coc,'explanation','CoC 설명',path);
  else if(['new_definitions','constraints'].includes(path)&&!root[path]?.length)host.append(el('p','현재 입력에 제약 정의가 없습니다. 관찰과 제약이 필요한 장면인지 확인하세요.'));
  else host.append(el('p','이 항목에는 전용 수정 입력이 아직 없습니다. 해당 생성 단계에서 입력을 검토하고 다시 검증하세요.'),editButton('관련 입력 열기',()=>openSource(editorSource)));
  if(item?.evidence_refs){const evidenceBox=el('details');evidenceBox.append(el('summary','연결된 관찰 근거 수정'));field(evidenceBox,item,'evidence_refs','검사에 사용할 관찰 근거',key+'['+index+'].evidence_refs',evidence(),{list:true});host.append(evidenceBox);}
  if(reviewDraft){host.append(el('p','여러 수정을 마친 뒤 아래 수정 반영 또는 반영 후 검증을 누르세요.'));batchPanel();return;}
  const kind=editorSource.component;
  if(kind==='sequence_coc'&&state.moment?.components.sequence_constraints)host.append(editButton('이어지는 제약 검토',()=>openReviewSource({moment_id:state.moment.id,component:'sequence_constraints',path:bundle.new_definitions?.length?'/new_definitions/0':bundle.facts?.length?'/facts/0':bundle.constraints?.length?'/constraints/0':'/new_definitions',value:clone(bundle.new_definitions?.[0]||bundle.facts?.[0]||bundle.constraints?.[0]||[])})));
  if(kind==='sequence_constraints'&&view?.input_diagnostics?.[state.moment?.id]?.constraint_binding)host.append(el('p',view.input_diagnostics[state.moment.id].constraint_binding));
  else if(kind==='sequence_constraints'&&state.moment?.components[kind]?.stale){host.append(el('p','CoC가 수정되어 제약의 연결을 다시 확인해야 합니다. 현재 설명·대상·조건이 수정한 CoC에도 맞는지 검토한 후 아래 버튼을 누르세요. 제약 내용과 모델 원문은 보존합니다.'));const refresh=editButton('새 CoC와 이 제약의 연결 확인',async()=>{if(state.busy)return;await save(kind);await flush();reviewEditor();controls();});refresh.dataset.reviewRefresh=kind;host.append(refresh);}
  if(same(kind)){const label=el('label','현재 입력이 모델 원문과 같습니다. 원문 그대로 수용');label.className='review_accept';const accept=el('input');accept.type='checkbox';accept.dataset.reviewAccept=kind;accept.checked=$('seq_accept_'+(kind==='sequence_coc'?'coc':'constraints')).checked;accept.onchange=()=>{$('seq_accept_'+(kind==='sequence_coc'?'coc':'constraints')).checked=accept.checked;save(kind).catch(error);};label.prepend(accept);host.append(label);}
  const approveButton=editButton('이 수정본 검토 완료',()=>work(async()=>{await approveReviewed(kind,true);showStage(4);controls();}));
  const diagnostics=view?.input_diagnostics?.[state.moment?.id];approveButton.disabled=!!diagnostics?.format_errors?.[kind]?.length||kind==='sequence_constraints'&&!!diagnostics?.constraint_binding;
  approveButton.dataset.reviewApprove=kind;const recheck=editButton('이 오류 수정 후 다시 검증',()=>work(()=>rerunDerived(editorSource?.review_moment_id)));recheck.dataset.reviewRecheck=kind;host.append(approveButton,recheck);
 }
 const detailOnly=item=>!item.property_failure&&(/^(B[1-8]|A[1-4])$/.test(item.code)||item.code==='PROPERTY_INPUT_REQUIRED');
 const pendingCodes=new Set(['EVIDENCE_MISSING','UNKNOWN_INPUT','UNRESOLVED_PREVIOUS','POSTCONDITION_UNKNOWN','PRECONDITION_UNKNOWN']);
 function compactReview(item,momentId){
  const lifecycle=lifecycleReview(item,momentId)||postconditionReview(item,momentId),sources=item.sources||[],pending=pendingCodes.has(item.code);
  const candidates=pending&&lifecycle?.pending.length?lifecycle.pending.map(r=>r.observation).filter(Boolean):sources.filter(s=>s.moment_id===momentId);
  const relevant=candidates.length?candidates:sources;
  const source=relevant.find(s=>s.component==='sequence_constraints'&&s.value?.truth==='UNKNOWN')||relevant.find(s=>s.value?.truth==='UNKNOWN')||relevant.find(s=>s.value?.code)||relevant[0];
  const uncertain=source?.value?.truth==='UNKNOWN';
  const simpleTitles={A1:'설명에 쓴 이유가 관찰 사실과 맞지 않습니다.',UNSUPPORTED_ATOM:'선택한 대상과 관계를 함께 사용할 수 없습니다.',ACTION_CONTRADICTION:'기록한 행동이 적용 중인 제약과 충돌합니다.',LIFECYCLE_CONFLICT:'제약의 시작과 해제가 동시에 확인됐습니다.',OBSERVATION_CONFLICT:'같은 사실의 확인 상태가 서로 다릅니다.',RELATION_CONTRADICTION:'대상 사이의 위치 관계가 서로 모순됩니다.',JUSTIFICATION_CONTRADICTION:'행동 설명에 쓴 이유가 관찰 사실과 맞지 않습니다.',CAN_ACTION_CONTRADICTION:'기록한 자차 행동이 CAN 속도와 맞지 않습니다.'};
  const title=pending?(source?readableStatement(source.value,source.entity_labels):'이 조건을 판단할 현재 관찰이 없습니다.'):(simpleTitles[item.code]||item.title||item.message||messages[item.code]);
  let suggestion=pending?(uncertain?'판단할 수 없음으로 유지할 수 있습니다. 이 결과는 모순이나 통과 판정이 아닙니다. 해제가 확인되지 않은 조건은 계속 유지합니다.':'현재 영상에서 확인 상태와 이유를 입력하세요. 영상으로 알 수 없으면 판단할 수 없음으로 남기세요.'):item.suggestions?.length?item.suggestions.map(s=>`‘${(s.field==='code'?names:truths)[s.before]||s.before}’ → ‘${(s.field==='code'?names:truths)[s.value]||s.value}’ (${s.basis})`).join(' / '):item.guidance||item.message||messages[item.code];
  if(!item.suggestions?.length){const simple={LIFECYCLE_CONFLICT:'통과 여부를 잘못 읽었다면 현재 관찰을 수정하세요. 두 관찰이 모두 맞다면 이전 제약을 완전히 지나치기 전까지만 적용하도록 수정하세요.',OBSERVATION_CONFLICT:'CoC와 제약의 같은 관찰 사실을 대조하고, 영상과 다른 확인 상태만 수정하세요.',ACTION_CONTRADICTION:'실제 행동을 잘못 읽었다면 CoC를 수정하세요. 행동이 맞다면 제약의 적용 대상과 조건을 확인하세요.'};suggestion=simple[item.code]||suggestion;}
  if(item.code==='UNSUPPORTED_ATOM'&&item.suggestions?.length)suggestion=(item.guidance||'대상 종류와 관계 연결을 확인하세요.')+' 확인 상태만 바꾸어도 대상 종류 오류는 남습니다. '+suggestion;
  return {pending,uncertain,source,title,suggestion,lifecycle,relevant};
 }
 function inspectionNotice(item,momentId){
  const pid=(item.property_ids||[])[0]||item.code,row=view?.stages?.verification?.result?.scenes.find(s=>s.moment_id===momentId),prop=row?.properties?.results.find(p=>p.property_id===pid);
  const checks=prop?.checks||[],notChecked=prop?.status==='NOT_CHECKED';
  let reason=checks.map(c=>c.message).filter(Boolean).join(' ')||'현재 입력만으로 검사 결과를 확정하지 못했습니다.';
  if(pid==='A1'){
   if(notChecked)reason='설명에서 어떤 이유가 어떤 행동을 설명하는지 연결되어 있지 않아 검사하지 못했습니다.';
   else if(checks.some(c=>c.message==='이유가 해당 행동의 조건과 연결되지 않았습니다.'))reason='설명에 쓴 이유가 기록된 행동의 이유인지, 현재 검사의 연결 기준으로는 판단하지 못했습니다.';
   else if(checks.some(c=>c.message==='설명 원문·실제 행동·이유의 연결을 확인하세요.'))reason='설명 문장, 실제 행동, 이유 중 연결이 빠지거나 맞지 않는 부분이 있어 판단하지 못했습니다.';
   else if(checks.some(c=>c.reason==='INPUT_CONFLICT'))reason='관찰 사실끼리 충돌해 설명에 쓴 이유가 맞는지 판단하지 못했습니다. 먼저 관찰 모순 항목을 확인하세요.';
   else if(checks.some(c=>c.reason==='SOLVER_UNKNOWN'))reason='검사기가 설명에 쓴 이유에 대한 결과를 확정하지 못했습니다.';
   else reason='설명에 쓴 이유가 맞는지 확인할 관찰 근거가 충분하지 않습니다.';
  }
  return {pid,prop,notChecked,reason,title:pid==='A1'?'설명에 쓴 이유와 행동의 연결을 확인하지 못했습니다.':reason};
 }
 function renderInspectionNotice(card,item,momentId){
  const info=inspectionNotice(item,momentId);card.dataset.inspectionStatus=info.prop?.status||'UNKNOWN';
  card.append(el('h3',(info.notChecked?'검사하지 못함':'판정 보류')+' · '+info.title),el('p',info.notChecked?'오류가 발견된 항목이 아니라, 검사에 필요한 연결이 없어 검사하지 못한 항목입니다.':'오류로 판정한 항목은 아닙니다. 이 검사만 판단을 보류했습니다.'));
  for(const source of item.sources||[]){const binding=source.value;if(!binding?.explanation_excerpt)continue;
   card.append(el('strong','검사한 CoC 문장'),el('blockquote',binding.explanation_excerpt));
   const actions=view?.stages?.eblc?.result?.scenes.find(s=>s.moment_id===momentId)?.observed_actions||[],action=actions[binding.action_index];
   if(action)card.append(el('p','기록된 행동: '+(names[action.code]||action.code)));
   const reasons=el('ul');for(const g of binding.reasons||[]){const a=g.atom,labels=source.entity_labels||{},subject=labels[a.subject_ref]||'관찰 대상',object=labels[a.object_ref]||'관찰 영역';let text=readableStatement(a,labels)+' · '+truths[g.expected_truth];
    if(a.predicate==='ZONE_CLOSED')text=`‘${subject}’의 통행이 ${g.expected_truth==='TRUE'?'막혀 있음':'막혀 있지 않음'}`;
    if(a.predicate==='IN')text=`‘${subject}’가 ‘${object}’ ${g.expected_truth==='TRUE'?'안에 있음':'안에 있지 않음'}`;
    reasons.append(el('li',text));}
   if(reasons.children.length)card.append(el('strong','설명에 쓴 이유'),reasons);
  }
  card.append(el('p','보류 이유: '+info.reason),el('p',info.notChecked?'이 검사를 수행하려면 CoC의 설명·행동·이유 연결을 보완해야 합니다. 미검사는 통과가 아닙니다.':'영상과 설명이 맞으면 그대로 둘 수 있습니다. 영상과 다른 부분을 발견한 경우에만 CoC를 수정하세요. 보류는 통과 판정이 아닙니다.'));
  const record=el('details');record.append(el('summary','검사 기록 보기'),el('p','관련 검사: '+info.pid),el('pre',JSON.stringify({status:info.prop?.status,checks:info.prop?.checks,sources:item.sources},null,2)));card.append(record);
 }
 function reviewItems(host,items,momentId=state.moment?.id){
  const secondary=(items||[]).filter(detailOnly),supplement=el('details');if(secondary.length){supplement.append(el('summary',`추가 검사에서 확인하지 못한 항목 · ${secondary.length}개`));}
  for(const [i,item] of (items||[]).entries()){
   const info=compactReview(item,momentId),card=el('article');card.className='review_item compact_review';card.dataset.code=item.code;card.id=item.issue_id||'review_'+momentId+'_'+i;card.tabIndex=-1;
   if(detailOnly(item)){renderInspectionNotice(card,item,momentId);supplement.append(card);continue;}
   card.append(el('h3',(info.pending?'판단 보류':'수정 필요')+' · '+info.title));
   if(!info.pending&&info.source)card.append(el('blockquote',readableStatement(info.source.value,info.source.entity_labels)));
   card.append(el('p','제안: '+info.suggestion));
   const actions=el('div');actions.className='review_compact_actions';
   const sources=new Map();
   for(const s of info.relevant)if(s.value?.predicate||s.value?.atom||s.value?.code||s.value?.condition_id||item.code==='MISSING_OBSERVED_ACTION')sources.set(s.component+sourcePath(s),s);
   for(const source of sources.values()){
    // Pending evidence only needs the unresolved observation, not the confirmed start condition.
    if(info.pending&&info.lifecycle&&info.lifecycle.pending.length&&!info.lifecycle.pending.some(r=>r.observation?.component===source.component&&sourcePath(r.observation)===sourcePath(source)))continue;
    const observation=observationInputs(info.lifecycle).find(r=>r.observation?.component===source.component&&sourcePath(r.observation)===sourcePath(source));
    const edit=editButton((source.moment_id!==momentId?'이전 제약 정의 수정':sources.size>1?'수정 · '+(source.component==='sequence_coc'?'CoC':'제약')+' '+reviewLocation(source):'수정 입력'),()=>openBatchSource({...source,observation_context:observation,formatError:item.code==='UNSUPPORTED_ATOM',lifecycleConflict:item.code==='LIFECYCLE_CONFLICT'},momentId));edit.dataset.batchSource=source.component;actions.append(edit);
   }
   if(!info.pending)for(const source of (item.sources||[]).filter(s=>s.moment_id!==momentId&&s.value?.condition_id)){const ordinal=state.moments.find(m=>m.id===source.moment_id)?.ordinal;const edit=editButton(`이전 제약 수정 · 시점 ${ordinal+1}`,()=>openBatchSource({...source,lifecycleConflict:item.code==='LIFECYCLE_CONFLICT'},momentId));edit.dataset.batchOrigin=source.moment_id;actions.append(edit);}
   for(const r of observationInputs(info.lifecycle).filter(r=>r.missing)){const b=editButton(observationButtonLabel(r),()=>openObservationInput(r.atom,true,r));b.dataset.batchObservation=r.atom.predicate;actions.append(b);}
   for(const suggestion of item.suggestions||[]){const b=editButton('제안으로 수정',async()=>{await openBatchSource({...suggestion.source,suggestion},momentId);await applyReviewSuggestion({...suggestion.source,batch:true,review_moment_id:momentId},suggestion);});b.dataset.batchSuggestion=suggestion.kind;actions.append(b);}
   if(info.uncertain){const b=editButton('미확인 유지',async()=>{card.querySelector('.review_keep_status')?.remove();const note=el('p','추가 근거가 생길 때까지 판단을 보류합니다. 입력 변경과 재검증은 필요하지 않습니다.');note.className='review_keep_status';card.append(note);});b.dataset.keepUnknown='true';actions.append(b);}
   card.append(actions);
   const details=el('details');details.className='review_details';details.append(el('summary','검사 상세 · 원문·근거'));
   const content=el('div');detailedReviewItems(content,[item],momentId);for(const c of content.children){c.className='review_detail_content';c.removeAttribute('id');c.removeAttribute('data-code');}details.append(content);card.append(details);(detailOnly(item)?supplement:host).append(card);
  }
  if(secondary.length)host.append(supplement);
 }
 function detailedReviewItems(host,items,momentId=state.moment?.id){
  const empty=v=>v==null||(Array.isArray(v)?!v.length:typeof v==='string'?!v.trim():typeof v==='object'&&!Object.keys(v).length);
  const ref=(s,id)=>s.entity_labels?.[id]||(coc?.entities||[]).find(e=>e.entity_id===id)?.description||'연결된 대상 없음';
  for(const [i,item] of (items||[]).entries()){
   const sources=item.sources||[],suggestions=item.suggestions||[],lifecycle=lifecycleReview(item,momentId)||postconditionReview(item,momentId),card=el('div');card.className='review_item';card.dataset.code=item.code;card.id=item.issue_id||'review_'+momentId+'_'+i;card.tabIndex=-1;
   card.append(el('h3',`문제 ${i+1} · ${item.title||item.message||messages[item.code]||'입력 확인 필요'}`));
   const step=(number,title)=>{const box=el('section');box.className='review_step';box.dataset.reviewStep=String(number);box.append(el('h4',`${number}. ${title}`));card.append(box);return box;};
   const original=step(1,'검사한 내용과 근거의 출처');
   for(const source of sources){const value=source.value,box=el('div');box.className='review_input_origin';const quote=el('blockquote');quote.className='review_problem_sentence';
    const sourceOrdinal=state.moments.find(m=>m.id===source.moment_id)?.ordinal;
    box.append(el('strong','실제 검사한 입력'),el('small',`${sourceOrdinal===undefined?'':'시점 '+(sourceOrdinal+1)+' · '}${source.component==='sequence_coc'?'CoC':'제약'} · ${reviewLocation(source)}${source.provenance?.input_revision!==undefined&&source.provenance?.input_revision!==null?' · 입력 버전 '+source.provenance.input_revision:''}`));
    if(empty(value))quote.append(el('p',item.code==='MISSING_OBSERVED_ACTION'?'실제로 확인한 자차 행동이 입력되지 않았습니다.':'검사 당시 이 항목은 입력되지 않았습니다.'));
    else{quote.append(el('p',readableStatement(value,source.entity_labels)));if(value.truth)quote.append(el('p','검사에 입력된 확인 상태: '+(truths[value.truth]||value.truth)));}
    box.append(quote);
    if(value?.evidence_note){const note=el('div');note.className='review_evidence_note';note.append(el('strong','이 입력에 붙은 근거 설명'),el('p',value.evidence_note),el('small',`출처: ${source.component==='sequence_coc'?'CoC':'제약'} · ${reviewLocation(source)} · 근거 설명${source.provenance?.note_origin==='MODEL_ORIGINAL'?' · 모델 생성 원문':' · 검사 당시 저장된 검토 입력'}`),el('p','위 문장은 관찰 근거의 설명입니다. 검사 대상은 위에 표시한 대상·관계·확인 상태입니다.'));box.append(note);}
    if(source.linked_frames?.length){const frames=el('div');frames.className='review_evidence_frames';
     for(const frame of source.linked_frames){const figure=el('figure'),label=`${({CURRENT:'현재',PREVIOUS:'이전',OTHER:'다른'})[frame.temporal_role]} 시점 ${frame.ordinal+1} · ${(frame.timestamp_us/1e6).toFixed(3)}초`;figure.dataset.temporalRole=frame.temporal_role;figure.append(el('figcaption',label));if(frame.asset_id){const image=el('img');image.src=API+'/assets/'+frame.asset_id;image.alt=label;image.loading='lazy';const enlarge=button('이 근거 영상 확대',()=>{$('zoom_image').src=image.src;$('zoom').showModal();});enlarge.append(image);figure.append(enlarge);}frames.append(figure);}
     box.append(el('p','모델이 연결한 근거 영상 · 작성 시점 기준으로 이전/현재를 구분합니다.'),frames,el('small','이전 영상에 나온 대상이 현재에도 보이거나 적용되는지는 따로 확인해야 합니다.'));}
    original.append(box);
   }
   if(!sources.length)original.append(el('p',item.message||messages[item.code]||'검사에 필요한 입력이 연결되지 않았습니다.'));
   const meaning=step(2,'문장의 의미와 문제');
   if(lifecycle){const table=el('table');table.className='property_table';table.dataset.lifecycleEvidence='true';const header=el('tr');for(const t of ['확인 항목','조건이 요구하는 상태','검사 결과','관찰 입력'])header.append(el('th',t));const head=el('thead');head.append(header);table.append(head);const body=el('tbody');
    for(const r of lifecycle.rows){const tr=el('tr');tr.dataset.guardPhase=r.label;tr.dataset.guardPredicate=r.atom.predicate;for(const t of [r.label+' · '+readableStatement(r.atom,r.labels),r.expected?truths[r.expected]:'연결된 기대값',({TRUE:'조건 묶음 성립',FALSE:'조건 묶음 불성립',UNKNOWN:'확인 필요',CONFLICT:'근거 충돌'})[r.status],r.missing?'관찰 사실이 없음':truths[r.observation.value.truth]])tr.append(el('td',t));body.append(tr);}
    if(lifecycle.actionCheck==='PASS'){const tr=el('tr');for(const t of ['제약과 기록 행동','—','모순 발견되지 않음','행동 수정 불필요'])tr.append(el('td',t));body.append(tr);}table.append(body);meaning.append(table,el('p',lifecycle.expectation?'이전 행동 뒤의 현재 영상에서 결과를 관찰하세요. 기대한 확인 상태와 실제 관찰 입력은 서로 다릅니다.':'시작 조건과 해제 조건은 서로 다른 사실입니다. 이미 확인된 시작 조건을 바꾸어 해제하지 마세요.'));
   }
   for(const source of lifecycle?[]:sources){const value=source.value,a=value?.atom||value;if(!a||typeof a!=='object'||Array.isArray(a))continue;
    const definitions=el('dl');definitions.className='review_meaning';const entry=(label,text)=>{definitions.append(el('dt',label),el('dd',text));};
    if(a.subject_ref){const type=source.entity_kinds?.[a.subject_ref];entry(value.code?'행동 주체':'관찰 대상',ref(source,a.subject_ref)+(type?' ('+(kinds[type]||type)+')':''));}
    if(a.object_ref)entry('비교·적용 대상',ref(source,a.object_ref));
    if(a.predicate)entry('확인하려는 관계',predicates[a.predicate]||a.predicate);
    if(value.code)entry('실제로 한 행동',names[value.code]||value.code);
    if(value.truth)entry('확인 상태의 뜻',({TRUE:'이 사실이 맞는 것으로 입력했습니다.',FALSE:'이 사실이 아니라는 것으로 입력했습니다.',UNKNOWN:'이 사실이 맞는지 아직 판단할 수 없습니다.',CONFLICT:'서로 다른 근거가 충돌합니다.'})[value.truth]);
    if(item.code==='POSTCONDITION_TIMING_REQUIRED'&&value.expected_postconditions){entry('결과를 연결한 행동',value.actions.map(a=>names[a]||a).join(', '));entry('현재 결과 확인 시점',value.postcondition_window==='NEXT_OBSERVATION'?'바로 다음 시점':'아직 정하지 않음');for(const g of value.expected_postconditions)entry('기대 결과',readableStatement(g,source.entity_labels)+' · '+({TRUE:'해당함',FALSE:'해당하지 않음'})[g.expected_truth]);}
    if(definitions.children.length)meaning.append(definitions);
   }
   meaning.append(el('p',item.guidance||item.message||messages[item.code]||'입력과 영상 근거를 대조하여 확인해야 합니다.'));if(item.limitation)meaning.append(el('p',item.limitation));
   const proposal=step(3,'수정 제안');
   if(lifecycle?.pending.length)for(const r of lifecycle.pending)proposal.append(el('p',`${r.label}을 판단할 관찰을 ${r.missing?'추가':'보완'}하세요: ${readableStatement(r.atom,r.labels)} 영상에서 확인한 상태를 입력하며, 판단하기 어려우면 미확인으로 남깁니다.`));
   for(const suggestion of suggestions){const box=el('div');box.className='repair_suggestion';const labels=suggestion.field==='code'?names:truths;
    box.append(el('strong',suggestion.kind==='COUNTEREXAMPLE_CANDIDATE'?'반례에 따른 수정 제안':'근거 문장에 따른 수정 제안'),el('p',`수정 전: ${labels[suggestion.before]||suggestion.before} → 수정 제안: ${labels[suggestion.value]||suggestion.value}`));
    const revised=clone(suggestion.source.value);revised[suggestion.field]=suggestion.value;
    box.append(el('p','수정 후 표현: '+(suggestion.field==='truth'?suggestion.value==='UNKNOWN'?'확인한 근거만으로는 이 사실이 맞는지 판단할 수 없다.':truths[suggestion.value]:readableStatement(revised,suggestion.source.entity_labels))),el('p','제안 근거: '+(suggestion.kind==='UNCERTAINTY_REVIEW'?'1번 근거 설명의 ‘확인하지 못했다’는 표현만으로 사실이 맞거나 틀리다고 확정할 수 없습니다. 판단할 근거가 부족하다는 뜻입니다.':suggestion.basis)),el('p',suggestion.message));proposal.append(box);
   }
   if(!suggestions.length&&!lifecycle?.pending.length){proposal.append(el('strong','직접 확인이 필요한 수정 제안'),el('p',(item.code==='UNSUPPORTED_ATOM'&&item.limitation?'표지의 적용 여부와 공사 구역 조건을 서로 다른 항목으로 분리하여 작성하는 것을 제안합니다. 현재 모델이 표지 대상을 지원하지 않아 올바른 대상 연결값을 확정할 수 없습니다. 근거 문장을 직접 다듬고 확인하지 못한 적용 여부는 판단할 수 없음으로 남겨 주세요.':item.certainty_guidance||item.guidance||item.message||messages[item.code]||'영상·CAN과 연결된 입력을 확인하고 잘못 읽힌 부분을 직접 편집하세요.')),el('p','현재 근거만으로 바꿀 값을 확정할 수 없어 승인할 자동 수정안은 없습니다. 아래 직접 편집으로 확인한 내용을 반영하세요.'));}
   const actions=step(4,'수정 승인 또는 직접 편집');
   if(lifecycle?.conflict){actions.append(el('p',`시점 ${state.moments.find(m=>m.id===momentId).ordinal+1}의 현재 관찰을 수정합니다. 이전 제약 정의의 수정은 아래 별도 버튼에서 선택하세요.`));const seen=new Set();for(const r of lifecycle.rows){const source=r.observation,key=source&&source.component+sourcePath(source);if(!source||seen.has(key))continue;seen.add(key);const edit=editButton(`${r.label} 관찰 수정 · ${reviewLocation(source)}`,()=>openReviewSource(source,momentId));edit.dataset.lifecycleObservation=r.atom.predicate;edit.dataset.observationComponent=source.component;actions.append(el('p',readableStatement(r.atom,r.labels)),edit);}}
   for(const r of observationInputs(lifecycle)){const b=editButton(r.missing?observationButtonLabel(r):'관찰 근거 보완',()=>openObservationInput(r.atom,false,r));b.className='structured_edit';b.dataset.inputObservation=r.atom.predicate;actions.append(el('p',readableStatement(r.atom,r.labels)),b);}
   for(const source of sources){if(lifecycle?.conflict&&source.moment_id===momentId&&!source.value?.condition_id&&!suggestions.some(s=>s.source.moment_id===source.moment_id&&s.source.component===source.component&&canonical(s.source.path)===canonical(source.path)))continue;const box=el('div');box.className='review_source';const ordinal=state.moments.find(m=>m.id===source.moment_id)?.ordinal;
    const location=`${ordinal===undefined?'연결 시점':`시점 ${ordinal+1}`} · ${source.component==='sequence_coc'?'CoC':'제약'} · ${reviewLocation(source)}`;box.append(el('p',location));
    const related=suggestions.filter(s=>s.source.moment_id===source.moment_id&&s.source.component===source.component&&canonical(s.source.path)===canonical(source.path));
    for(const suggestion of related){const accept=editButton('수정 제안 승인·반영',()=>applyReviewSuggestion({...source,review_moment_id:momentId},suggestion));accept.dataset.acceptSuggestion=suggestion.kind;box.append(accept);}
    const edit=button(lifecycle?.conflict&&source.value?.condition_id?'원래 제약 정의 수정':item.code==='MISSING_OBSERVED_ACTION'?'실제 행동 입력':'직접 편집',()=>openReviewSource({...source,...(lifecycle?.conflict?{lifecycleConflict:true}:{}),...(related[0]?{suggestion:related[0]}:{})},momentId));edit.dataset.reviewSuggestion=related[0]?.kind||'MANUAL';box.append(edit);
    if(empty(source.value))box.append(el('p',item.code==='MISSING_OBSERVED_ACTION'?'검사 당시 실제 행동 항목이 입력되지 않았습니다. CoC 설명과 별도로 영상·CAN을 확인하세요.':'검사 당시 이 항목은 입력되지 않았습니다.'));
    else{const detail=el('details');detail.append(el('summary','검사에 사용한 원문 보기'),el('pre',typeof source.value==='string'?source.value:JSON.stringify(source.value,null,2)));box.append(detail,el('p',`관찰 근거: ${source.evidence_refs?.length?source.evidence_refs.length+'개 연결됨':'추가 확인 필요'}`));}
    actions.append(box);
   }
   if(!sources.length)actions.append(el('p','수정 위치가 연결되지 않았습니다. 해당 입력·완료 시점을 확인한 후 다시 검증하세요.'));
   if(suggestions.length)actions.append(el('small','제안 승인은 해당 입력의 수정에 대한 승인입니다. 검토 완료 → EBLC 생성 → 재검증 후 해결 여부를 확인합니다.'));
   for(const cid of new Set(sources.map(s=>s.value?.condition_id).filter(Boolean))){
    if(!view?.stages?.eblc?.result?.scenes.find(x=>x.moment_id===momentId)?.constraints.some(d=>d.condition_id===cid))continue;
    const link=editButton('제약 도식 보기',async()=>{if(state.busy)return;if(momentId!==state.moment?.id){await loadMoment(momentId);await render();}diagramId=cid;showStage(3);renderDerived();$('seq_diagram_card').scrollIntoView({block:'center'});});link.dataset.showDiagram=cid;actions.append(link);
   }
   if(item.property_ids?.length)card.append(el('small','관련 검사: '+item.property_ids.join(', ')));host.append(card);
  }
 }
 function quality(){
  const host=$('seq_quality');host.replaceChildren();if(!view?.quality)return;
  host.append(el('h3','모델 첫 제안과 검토 후 결과'));
   for(const [key,label] of [['first_pass','모델 첫 제안'],['reviewed','검토 후 현재 결과']]){let q=view.quality[key];if(key==='reviewed'&&view.stages?.verification?.review_summary)q=view.stages.verification.review_summary.counts.authored_results;if(!q)continue;const card=el('div');card.className='quality_summary';card.append(el('strong',label));if(key==='reviewed'&&(dirty||view.stages?.verification?.stale)){card.append(el('p','현재 입력의 검증 결과는 아직 없습니다. 위의 검증 실행 안내를 확인하세요.'));host.append(card);continue;}const rate=q.total>0&&q.pass_rate!==null&&q.pass_rate!==undefined?`${(q.pass_rate*100).toFixed(1)}%`:'산출 전';card.append(el('p',`평가한 시점 ${q.total}개 · 일치 ${q.pass}개 (${rate}) · 모순 ${q.contradiction}개 · 확인 필요 ${q.review_required}개`));host.append(card);if(key==='first_pass')originalQualityDetails(card);}
  if(view.quality.pending||view.quality.generation_failures)host.append(el('p',`최초 제안 검사 대기 ${view.quality.pending||0}개 · 결과가 설치되지 않은 생성 ${view.quality.generation_failures||0}개`));
  if(view.quality.not_generated)host.append(el('p',`모델 첫 제안 평가에 연결되지 않은 시점 ${view.quality.not_generated}개 · 첫 제안 평가에서 제외`));
  const assisted=(view.quality.items||[]).filter(i=>i.human_assisted_pair||i.first_pass?.codes?.includes('HUMAN_ASSISTED_PAIR')).length;if(assisted)host.append(el('p',`사람이 CoC를 수정한 뒤 제약을 생성한 시점 ${assisted}개 · 모델만의 일치로 세지 않습니다.`));
  host.append(el('p','위 개수는 속성이나 오류 개수가 아니라 평가한 시점 수입니다. 모델 첫 제안은 생성 당시 입력의 평가 이력이며 수정·재검증으로 바뀌지 않습니다. 현재 수정할 항목은 위의 현재 입력 검증 결과에서 확인하세요.'));
 }
 function originalQualityDetails(host){
  const item=view.quality.items?.find(i=>i.moment_id===state.moment?.id),result=item?.first_pass;
  if(!result||!item.pair_id)return;
  const box=el('section');box.dataset.originalQuality='true';box.append(el('h4',`시점 ${item.ordinal+1} · 최초 제안 평가: ${statuses[result.status]||'확인 필요'}`),el('p','생성 당시 평가 · 읽기 전용 이력입니다. 현재 검증 결과와 구분해서 확인하세요.'));
  const labels=Object.fromEntries((data('sequence_constraints').original_coc?.entities||original('sequence_coc')?.entities||[]).map(e=>[e.entity_id,e.description||kinds[e.kind]]));
  for(const finding of result.review_items||[]){
   const detail=el('div');detail.dataset.firstReview=finding.code;detail.append(el('strong',finding.message||messages[finding.code]||'입력 확인 필요'));
   for(const source of finding.sources||[]){const v=source.value;
    detail.append(el('p',`${source.component==='sequence_coc'?'CoC':'제약'} · ${reviewLocation(source)}: ${v?.description||v?.evidence_note||readableStatement(v,labels)}`));
    if(v?.condition_id){const phase=result.properties?.results?.find(p=>p.property_id==='B5')?.checks?.find(c=>c.condition_id===v.condition_id);
     for(const [key,label] of [['activation_all_of','조건이 시작되는 때'],['release_any_of','조건이 끝나는 때']])if(v[key]?.length)detail.append(el('p',label+': '+v[key].map(g=>readableStatement({...g.atom,truth:g.expected_truth},labels)+' · '+truths[g.expected_truth]).join(', ')));
     if(phase?.state==='ACTIVE'&&phase.release_guard==='UNKNOWN')detail.append(el('p','시작 조건은 확인됐지만 해제 조건을 확인할 관찰이 연결되지 않았습니다. 해제가 확인될 때까지 이 제약을 유지합니다. 확인되지 않은 사실을 해당하지 않음으로 바꾸어 해제하지 마세요.'));
    }
   }
   box.append(detail);
  }
  const covered=new Set((result.review_items||[]).map(i=>i.code));
  for(const p of result.properties?.results||[])if(['UNKNOWN','NOT_CHECKED','FAIL'].includes(p.status)&&!p.checks?.some(c=>covered.has(c.code))){const message=p.property_id==='B8'?'행동 뒤의 결과를 검사할 시점·관찰 연결 정보가 충분하지 않아 검사하지 못했습니다.':p.message;const line=el('p',`${p.title}: ${p.status==='NOT_CHECKED'?'검사하지 못함':p.status==='FAIL'?'모순 발견':'확인 필요'} · ${message}`);line.dataset.firstProperty=p.property_id;box.append(line);}
  if(!result.review_items?.length&&result.status!=='PASS')for(const code of result.codes||[])box.append(el('p',messages[code]||'최초 제안을 평가할 입력 또는 근거가 부족합니다.'));
  host.append(box);
 }
 let diagramMoment=null,diagramId=null,diagramMove=null,diagramTouch=null;
 const lifecycle={ACTIVE:'활성',RELEASED:'해제',UNKNOWN:'미확인',CONFLICT:'근거 충돌'};
 function diagram(compiled,previous,verified,{outdated=false,verificationOutdated=false}={}){
  const list=$('seq_diagram_list'),card=$('seq_diagram_card'),items=compiled?.constraints||[];
  if(diagramMoment!==state.moment?.id){diagramMoment=state.moment?.id;diagramId=null;}
  list.replaceChildren();card.replaceChildren();diagramMove=null;
  $('seq_diagram_content').hidden=!items.length;$('seq_diagram_empty').hidden=!!items.length;
  $('seq_diagram_empty').textContent=compiled?'이 시점의 EBLC에 표시할 제약이 없습니다.':'EBLC를 생성하면 제약 도식이 표시됩니다.';
  $('seq_diagram_notice').textContent=outdated?'이전 생성 결과입니다. 현재 입력으로 EBLC를 다시 생성하세요.':'저장된 EBLC의 조건 흐름입니다. 제약을 직접 넘겨서 검토하세요.';
  if(!items.length)return;
  if(!items.some(d=>d.condition_id===diagramId))diagramId=items[0].condition_id;
  const index=items.findIndex(d=>d.condition_id===diagramId),d=items[index],modern=Array.isArray(d.activation_all_of);
  const checked=!outdated&&!verificationOutdated?verified:null;
  const query=checked?.verification?.condition_checks?.results.find(q=>q.query_id==='condition_'+d.condition_id);
  const related=(checked?.review_items||[]).filter(item=>(item.sources||[]).some(s=>s.value?.condition_id===d.condition_id));
  function conditionResult(cid){
   if(outdated||verificationOutdated)return ['STALE',outdated?'재생성·재검증 필요':'재검증 필요'];
   if(!checked)return ['UNVERIFIED','미검증'];
   const q=checked.verification?.condition_checks?.results.find(x=>x.query_id==='condition_'+cid);
   if(q?.status==='UNSAT')return ['CONTRADICTION','모순 발견'];
   if(checked.status==='PASS')return ['PASS','입력 조건 안에서 일치'];
   return ['REVIEW_REQUIRED',checked.status==='CONTRADICTION'?'장면 모순 · 관련 항목 확인':'확인 필요'];
  }
  diagramMove=offset=>{diagramId=items[(index+offset+items.length)%items.length].condition_id;diagram(compiled,previous,verified,{outdated,verificationOutdated});};
  items.forEach((item,i)=>{
   const [code,label]=conditionResult(item.condition_id),b=el('button');b.type='button';b.dataset.conditionId=item.condition_id;b.dataset.status=code;
   b.setAttribute('aria-current',String(i===index));b.append(el('span',`${i+1}. ${item.description}`),el('small',label));
   b.onclick=()=>{diagramId=item.condition_id;diagram(compiled,previous,verified,{outdated,verificationOutdated});[...list.children].find(x=>x.dataset.conditionId===diagramId)?.focus({preventScroll:true});};list.append(b);
  });
  $('seq_diagram_position').textContent=`제약 ${index+1} / ${items.length}`;$('seq_diagram_prev').disabled=$('seq_diagram_next').disabled=items.length<2;
  card.dataset.conditionId=d.condition_id;card.append(el('p',classes[d.condition_class]||'분류 미지정'),el('h3',d.description));
  const info=compiled.states?.[d.condition_id],prior=info?.prior_state||previous?.ledger?.[d.condition_id],now=info?.state||compiled.ledger?.[d.condition_id];
  const continuation=el('div');continuation.className='eblc_continuity';
  continuation.append(el('strong',previous?.ledger?.[d.condition_id]!==undefined?'이전 장면에서 이어짐':'이 시점에서 시작'));
  continuation.append(el('p',`${prior?lifecycle[prior]||prior:'이전 상태 없음'} → ${lifecycle[now]||now||'미확인'}`));
  if(info?.carried_active_without_confirmed_release)continuation.append(el('p','해제 근거가 확인되지 않아 이전 제약을 유지합니다.'));
  if(info?.state==='CONFLICT'&&info.active_obligation)continuation.append(el('p','근거가 충돌하지만 이전의 활성 제약은 유지됩니다.'));
  card.append(continuation);
  const flow=el('ol');flow.className='eblc_flow';
  function node(title,lines,stateLabel){const n=el('li');n.className='eblc_flow_node';n.append(el('h4',title));for(const line of lines)n.append(el('p',line));if(stateLabel)n.append(el('small',stateLabel));flow.append(n);return n;}
  const entities=[...(compiled.property_input?.inherited_entities||[]),...(previous?.property_input?.moment?.coc?.entities||[]),...(compiled.property_input?.moment?.coc?.entities||[])];
  const labels=entities.length?Object.fromEntries(entities.map(e=>[e.entity_id,e.description||kinds[e.kind]||'대상'])):refs();
  const ref=id=>id?labels[id]||'대상 연결 확인 필요':'미지정';
  const guardLines=gs=>gs?.length?gs.map(g=>`${ref(g.atom.subject_ref)}${g.atom.object_ref?' → '+ref(g.atom.object_ref):''} · ${predicates[g.atom.predicate]||g.atom.predicate} · ${g.expected_truth==='TRUE'?'사실임을 확인':'사실이 아님을 확인'}`):['확인 조건 미지정'];
  const target=modern?[`행동 주체: ${ref(d.subject_ref)}`,`제약 원인 대상: ${(d.condition_target_refs||[]).map(ref).join(', ')||'미지정'}`,`행동 대상: ${ref(d.action_target_ref)}`,...(d.movement_ref&&d.movement_ref!==d.subject_ref?[`진행 경로: ${ref(d.movement_ref)}`]:[])]:[`적용 범위: ${d.scope_id||'미지정'}`,'기존 형식에는 대상·관계가 구조화되지 않았습니다.'];
  node('대상·관계',target);
  node(modern?'발동 · 아래 조건 모두 확인':'발동 조건',modern?guardLines(d.activation_all_of):[d.activation],info?`현재 확인: ${truths[info.activation_guard]||'미확인'}`:null);
  const action=node('행동 제약',[`${(d.actions||[]).map(a=>names[a]||a).join(', ')} · ${effects[d.effect]||d.effect}`,modern?'확인된 해제 전까지 유지':`유지: ${d.hold}`,...(d.effect==='ALLOW'?['이 제약의 조건부 허용입니다. 다른 제약도 함께 확인해야 합니다.']:[])]);
  if(modern&&d.preconditions?.length){const details=el('details');details.append(el('summary','행동 전에 필요한 조건'),el('p',guardLines(d.preconditions).join('\n')));action.append(details);}
  if(modern&&d.expected_postconditions?.length){const details=el('details');details.append(el('summary','다음 장면에서 확인할 기대 결과'),el('p',guardLines(d.expected_postconditions).join('\n')));action.append(details);}
  node(modern?'해제 · 아래 조건 중 하나 확인':'해제 조건',modern?guardLines(d.release_any_of):[d.release],info?`현재 확인: ${truths[info.release_guard]||'미확인'}`:null);
  card.append(flow);
  const outcome=el('div'),[resultCode,resultLabel]=conditionResult(d.condition_id);outcome.className='eblc_diagram_result';outcome.dataset.status=resultCode;
  outcome.append(el('strong',resultLabel));
  if(query?.status==='SAT'&&checked?.status!=='PASS')outcome.append(el('p','이 제약의 개별 행동 검사는 일치합니다. 장면 전체의 확인 항목은 남아 있습니다.'));
  for(const item of related)outcome.append(el('p',item.message||messages[item.code]||item.code));
  if(checked&&!related.length&&resultCode==='REVIEW_REQUIRED')outcome.append(el('p','장면 전체의 검증 결과에서 관련 근거를 확인하세요.'));
  if(!checked&&!outdated&&!verificationOutdated)outcome.append(el('p','EBLC 생성은 완료됐습니다. 검증을 실행하면 결과가 표시됩니다.'));
  outcome.append(el('p',`현재 관찰 행동: ${(compiled.observed_actions||[]).map(a=>typeof a==='string'?names[a]||a:`${names[a.code]||a.code}${a.action_target_ref?' → '+ref(a.action_target_ref):''}`).join(', ')||'미확인'}`));
  card.append(outcome);
  if(!outdated){
   let source=Object.values(compiled.source_map||{}).find(s=>s.component==='sequence_constraints'&&s.value?.condition_id===d.condition_id);
   if(!source&&!modern){const i=bundle?.constraints?.findIndex(x=>x.condition_id===d.condition_id);if(i>=0)source={moment_id:state.moment.id,component:'sequence_constraints',path:`/constraints/${i}/description`};}
   if(source){const edit=editButton('제약 수정',()=>openSource(source));edit.dataset.diagramEdit=d.condition_id;card.append(edit);}
  }
  const evidenceBox=el('details');evidenceBox.append(el('summary','관찰 근거·규칙 출처'));
  const atoms=modern?[...d.activation_all_of,...d.release_any_of,...d.preconditions,...d.expected_postconditions].map(g=>canonical(g.atom)):[];
  const sources=Object.values(compiled.source_map||{}).filter(s=>s.value?.condition_id===d.condition_id||atoms.includes(canonical(s.value?.atom||{predicate:s.value?.predicate,subject_ref:s.value?.subject_ref,object_ref:s.value?.object_ref})));
  const evidenceRefs=[...new Set(modern?sources.flatMap(s=>s.evidence_refs||[]):d.evidence_refs||[])];
  evidenceBox.append(el('p',`관찰 근거: ${evidenceRefs.join(', ')||'연결된 근거 없음'}`),el('p',`규칙 출처: ${(d.source_refs||[]).join(', ')||'별도 확인 필요'}`));card.append(evidenceBox);
 }
 bind('seq_diagram_prev',()=>diagramMove?.(-1));bind('seq_diagram_next',()=>diagramMove?.(1));
 $('seq_eblc_diagram').addEventListener('keydown',event=>{
  if(!['ArrowLeft','ArrowRight'].includes(event.key)||!event.target.closest('.eblc_diagram_nav')&&event.target!==$('seq_eblc_diagram'))return;
  event.preventDefault();diagramMove?.(event.key==='ArrowRight'?1:-1);
 });
 $('seq_diagram_card').addEventListener('pointerdown',event=>{diagramTouch=event.pointerType==='touch'?{x:event.clientX,y:event.clientY,id:event.pointerId}:null;});
 $('seq_diagram_card').addEventListener('pointercancel',()=>{diagramTouch=null;});
 $('seq_diagram_card').addEventListener('pointerup',event=>{const start=diagramTouch;diagramTouch=null;if(!start||start.id!==event.pointerId||event.target.closest('button,summary'))return;const dx=event.clientX-start.x,dy=event.clientY-start.y;if(Math.abs(dx)>=60&&Math.abs(dy)<40)diagramMove?.(dx<0?1:-1);});

 const reviewStatuses={NOT_CREATED:'작성 대기',REVIEW_REQUIRED:'입력·근거 확인 필요',CONTRADICTION:'모순 발견',SOURCE_REVIEW:'논리 검사 일치 · 출처 별도 확인',PASS:'입력 조건 안에서 일치'};
 function reviewReport(summary,result){
  const current=$('seq_current_result'),all=$('seq_scene_results'),common=$('seq_common_review'),pairs=$('seq_pair_rows');
  current.replaceChildren();all.replaceChildren();common.replaceChildren();pairs.replaceChildren();
  if(!summary)return;
  const c=summary.counts;
  $('seq_scope_status').textContent=`작성된 시점 ${c.authored}/${c.total}개 · 모순 ${c.contradictions}개 · 연속 검사 ${c.checked_pairs}쌍 / 작성·검토 대기 ${c.pending_pairs}쌍`;
  for(const notice of summary.source_notices){const box=el('div');box.className='review_common_notice';box.dataset.code=notice.code;box.append(el('strong','규칙 출처 · 별도 검토'),el('p',notice.message));common.append(box);}
  if(c.not_created)common.append(el('p',`미작성 ${c.not_created}개 시점은 작성 대기로 묶었습니다. 이어받은 조건은 보존하지만, 현재 행동과의 비교 및 연속 검사는 아직 완료되지 않았습니다.`));
  const range=s=>s.from_ordinal===s.to_ordinal?`시점 ${s.from_ordinal+1}`:`시점 ${s.from_ordinal+1}–${s.to_ordinal+1} (${s.count}개)`;
  function card(s,heading,withActions){
   const div=el('div');div.className='scene_result';div.dataset.reviewStatus=s.display_status;if(!withActions)div.append(el('strong',`${heading} · ${reviewStatuses[s.display_status]||s.display_status}`));
   if(s.input_status==='NOT_CREATED'){
    div.append(el('p','작성 대기 · CoC와 제약이 아직 작성되지 않았습니다.'));if(withActions)reviewItems(div,s.issues,s.moment_id);else for(const issue of s.issues)div.append(el('p',issue.message||messages[issue.code]||issue.code));
    if(withActions)div.append(editButton('CoC 작성으로 이동',()=>openSource({moment_id:s.moment_id,component:'sequence_coc',path:'/explanation'})));
   }else{
    if(withActions)reviewItems(div,s.issues,s.moment_id);else for(const issue of s.issues)div.append(el('p',issue.message||messages[issue.code]||issue.code));
    if(!s.issues.length)div.append(el('p',s.display_status==='SOURCE_REVIEW'?'입력한 행동과 제약의 논리 검사는 일치합니다. 규칙 출처 확인은 위 안내에서 별도로 진행하세요.':'입력한 행동과 제약을 검사했습니다.'));
   }
   return div;
  }
  const point=summary.scenes.find(s=>s.moment_id===state.moment?.id);
  if(point){
   const primary=point.issues.filter(i=>!detailOnly(i)),pending=primary.filter(i=>pendingCodes.has(i.code)).length;
   $('seq_result_status').textContent=point.input_status==='NOT_CREATED'?`시점 ${point.ordinal+1} · 작성 대기`:`시점 ${point.ordinal+1} · 수정 필요 ${primary.length-pending}개 · 판단 보류 ${pending}개`;
   current.append(card(point,`시점 ${point.ordinal+1}`,true));if(point.input_status!=='NOT_CREATED')propertyReport(current,result.scenes.find(s=>s.moment_id===point.moment_id),point);
  }
  for(const group of summary.scene_groups){
   const div=card(group,range(group),false);
   if(group.input_status!=='NOT_CREATED')div.append(editButton('이 시점 검토',async()=>{if(state.busy)return;await loadMoment(group.moment_id);showStage(4);}));
   all.append(div);
  }
  for(const p of summary.pair_groups){
   const tr=el('tr'),range=p.count===1?`${p.from_ordinal+1} → ${p.to_ordinal+1}`:`${p.from_ordinal+1} → ${p.from_ordinal+2} … ${p.to_ordinal} → ${p.to_ordinal+1} (${p.count}쌍)`;
   const label=p.status==='WAITING'?'작성·검토 대기':reviewStatuses[p.status]||statuses[p.status]||p.status;
   const note=p.status==='WAITING'?'두 시점의 CoC·제약·관찰 행동과 검토가 준비되면 비교합니다.':p.codes.map(code=>messages[code]||code).join(' ')||'장면 간 입력 조건이 일치합니다.';
   for(const text of [range,`${p.carried_ids.length}개`,label,note])tr.append(el('td',text));pairs.append(tr);
  }
  $('seq_pending').textContent=`영상 끝에 남은 조건 ${result.pending.length}개 · 남은 조건은 유지하며, 미작성 장면의 행동을 추정하지 않습니다.`;
 }

 function propertyReport(host,row,point=null){
  if(!row?.properties)return;
  const p=row.properties,box=el('details');box.append(el('summary','12개 속성 검사 · 상세 결과'));box.className='property_report';box.dataset.propertyStatus=p.status;
  const labels={PASS:'일치',FAIL:'위반',UNKNOWN:'확인 필요',NOT_CHECKED:'미검사',NOT_APPLICABLE:'해당 없음'},categories={SAFETY:'Safety · 안전 제약',CONSISTENCY:'Consistency · 일관성',GROUNDING:'Grounding · 근거',COVERAGE:'Coverage · 조건 포함'};
  box.append(el('h3','12개 속성 검사'),el('p',`일치 ${p.counts.PASS} · 위반 ${p.counts.FAIL} · 확인 필요 ${p.counts.UNKNOWN} · 미검사 ${p.counts.NOT_CHECKED} · 해당 없음 ${p.counts.NOT_APPLICABLE}`),el('p','바로 이전·현재 장면과 유지 조건만 검사합니다. 미검사·확인 필요는 통과로 집계하지 않습니다.'));
  const table=el('table');table.className='property_table';const head=el('thead'),tr=el('tr');for(const text of ['분류','속성','결과','확인 내용'])tr.append(el('th',text));head.append(tr);table.append(head);const body=el('tbody');
  for(const prop of p.results){const r=el('tr');r.dataset.propertyId=prop.property_id;r.dataset.propertyStatus=prop.status;r.append(el('td',categories[prop.category]||prop.category),el('td',`${prop.property_id} · ${prop.property_id==='A1'?'설명에 쓴 이유가 맞는지':prop.title}`),el('td',labels[prop.status]||prop.status));const a1Message=prop.status==='PASS'?'설명에 쓴 이유가 입력한 관찰 사실과 일치합니다.':prop.status==='FAIL'?'설명에 쓴 이유가 입력한 관찰 사실과 맞지 않습니다.':inspectionNotice({code:'A1'},row.moment_id).reason;const detail=el('td',prop.property_id==='A1'?a1Message:prop.message);
   for(const check of prop.checks||[]){if(check.permission)detail.append(el('p',`허용 판단: ${({CONFIRMED:'확인됨',BLOCKED:'보류',UNCONFIRMED:'미확인'})[check.permission]}`));if(check.missing?.length)detail.append(el('p','빠진 조건: '+check.missing.map(x=>`${predicates[x.predicate]||x.predicate} (${refs()[x.target||x.signal]||'대상 연결 확인 필요'})`).join(', ')));if(check.message&&check.message!==prop.message&&!check.code)detail.append(el('p',check.message));
    if(prop.property_id==='B8'&&check.reason){const source=check.sources?.[0],d=source?.value,info=el('div');info.dataset.postconditionReason=check.reason;
     if(d){info.append(el('strong',d.description),el('p','결과를 연결한 행동: '+d.actions.map(a=>names[a]||a).join(', ')),el('p','이전 기록 행동: '+(check.previous_actions.map(a=>names[a.code]||a.code).join(', ')||'기록 없음')),el('p','현재 기록 행동: '+(check.current_actions.map(a=>names[a.code]||a.code).join(', ')||'기록 없음')));for(const g of d.expected_postconditions)info.append(el('p','기대 결과: '+readableStatement(g,source.entity_labels)+' · '+({TRUE:'해당함',FALSE:'해당하지 않음'})[g.expected_truth]));}
     if(check.reason==='NEXT_SCENE_PENDING'){const next=state.moments.find(m=>m.ordinal===row.ordinal+1);if(next)info.append(editButton('다음 시점 열기',async()=>{if(state.busy)return;await flush();await loadMoment(next.id);await render();showStage(1);}));else info.append(el('p','마지막 시점이므로 이어지는 결과 영상이 없습니다. B8 통과로 집계하지 않습니다.'));}
     detail.append(info);
    }
   }
   for(const iid of point?.property_issue_ids?.[prop.property_id]||[]){const number=point.issues.findIndex(i=>i.issue_id===iid)+1;const finding=point.issues.find(i=>i.issue_id===iid);const link=editButton(finding&&detailOnly(finding)?'검사 보류 이유 보기':`문제 ${number} 보기`,async()=>{const card=document.getElementById(iid);for(let a=card?.parentElement;a;a=a.parentElement)if(a.tagName==='DETAILS')a.open=true;card?.scrollIntoView({block:'center'});card?.focus({preventScroll:true});});link.dataset.issueLink=iid;detail.append(link);}
   const raw=el('details');raw.append(el('summary','검사식·반례 보기'),el('pre',JSON.stringify(prop.checks,null,2)));if(prop.checks?.length)detail.append(raw);r.append(detail);body.append(r);
  }table.append(body);box.append(table);host.append(box);
 }

 function renderDerived(){
  const e=view?.stages?.eblc,v=view?.stages?.verification,n=view?.stages?.cnl;quality();
  const stale=s=>dirty||(s?.stale&&!['QUEUED','RUNNING','FAILED'].includes(s.job_status));
  const currentScene=s=>s?.result?.scenes.find(x=>x.moment_id===state.moment?.id);
  const compiled=e?.job_status==='SUCCEEDED'&&!stale(e)?currentScene(e):null;
  const next=inputStep(),changed='입력이 바뀌었습니다. '+next.text;
  $('seq_eblc_status').textContent=stale(e)?changed:e?.job_status==='SUCCEEDED'?`${e.result.scenes.length}개 시점의 EBLC 생성 완료`:e?.job_status==='FAILED'?'EBLC 생성에 실패했습니다. 다시 실행하세요.':['QUEUED','RUNNING'].includes(e?.job_status)?'EBLC 생성 중…':next.text;
  $('seq_eblc_text').textContent=compiled?JSON.stringify(compiled.core,null,2):'아직 생성된 EBLC가 없습니다.';
  if(!compiled)$('seq_eblc_raw').open=false;
  const previous=compiled?e?.result?.scenes.find(x=>x.ordinal===state.moment?.ordinal-1):null;
  diagram(compiled,previous,currentScene(v),{outdated:!!stale(e),verificationOutdated:!!stale(v)||!!v&&v.job_status!=='SUCCEEDED'});
  $('seq_result_status').textContent=stale(v)?'입력이 바뀌었습니다. 이전 검사 결과는 현재 수정본의 결과가 아닙니다.':v?.job_status==='FAILED'?'검증 작업이 완료되지 않았습니다. 검증 실행을 다시 누르세요.':['QUEUED','RUNNING'].includes(v?.job_status)?'검증 중…':v?.result?`전체 결과: ${statuses[v.result.status]}`:next.text;
  const row=currentScene(v);$('seq_current_result').replaceChildren();$('seq_scene_results').replaceChildren();$('seq_pair_rows').replaceChildren();$('seq_scope_status').textContent='';
  function resultRow(s){const div=el('div');div.className='scene_result';div.append(el('strong',`시점 ${s.ordinal+1} · ${statuses[s.status]}`));for(const c of s.codes||[])div.append(el('p',messages[c]||c));if(!s.codes?.length)div.append(el('p',s.status==='PASS'?'지원되는 관찰 행동과 입력 조건이 일치합니다.':'확인할 관찰 또는 조건이 부족합니다.'));if(s.source_status)div.append(el('p',`규칙·법적 출처 검토: ${['GROUNDED','VERIFIED'].includes(s.source_status)?'출처 확인됨':'별도 확인 필요'} (${s.source_status})`));reviewItems(div,s.review_items,s.moment_id);return div;}
  if(row&&!stale(v)){$('seq_current_result').append(resultRow(row));propertyReport($('seq_current_result'),row);}
  if(v?.result&&!stale(v)){for(const s of v.result.scenes)$('seq_scene_results').append(resultRow(s));for(const p of v.result.pairs){const tr=el('tr');for(const text of [`${p.from_ordinal+1} → ${p.to_ordinal+1}`,`${p.carried_ids.length}개`,statuses[p.status],p.codes.map(c=>messages[c]||c).join(' ')||'모순 없음'])tr.append(el('td',text));$('seq_pair_rows').append(tr);}}
  $('seq_pending').textContent=v?.result&&!stale(v)?`영상 끝에 남은 조건 ${v.result.pending.length}개 · 남아 있다는 사실만으로 위반은 아닙니다.`:'';
  $('seq_common_review').replaceChildren();if(v?.review_summary&&!stale(v))reviewReport(v.review_summary,v.result);
  correctionResults(v);
  const sample=n?.result?.samples.find(x=>x.moment_id===state.moment?.id);
  $('seq_cnl_text').textContent=displayProse(stale(n)?changed:n?.job_status==='FAILED'?'CNL 생성에 실패했습니다. 다시 실행하세요.':['QUEUED','RUNNING'].includes(n?.job_status)?'CNL 생성 중…':sample?.text||'아직 생성된 CNL이 없습니다.');
  $('seq_cnl_verification').hidden=!sample?.verification_text||!!stale(n)||n?.job_status!=='SUCCEEDED';
  $('seq_cnl_verification_text').textContent=$('seq_cnl_verification').hidden?'':sample.verification_text;
  if($('seq_cnl_verification').hidden)$('seq_cnl_verification').open=false;
  $('seq_cnl_details').hidden=!sample?.constraint_details||!!stale(n)||n?.job_status!=='SUCCEEDED';
  $('seq_cnl_details_text').textContent=$('seq_cnl_details').hidden?'':sample.constraint_details;
  if($('seq_cnl_details').hidden)$('seq_cnl_details').open=false;
  correctionFlow();
  $('seq_recheck_saved').hidden=!view?.stages?.verification?.stale||!approved('sequence_coc')||!approved('sequence_constraints');
  $('seq_recheck_saved').disabled=state.busy||draftChanged();
 }
 function correctionResults(v){
  const review=v?.correction_review;if(!review?.changed_inputs.length)return;
  const issues=review.issues.filter(issue=>issue.moment_id===state.moment?.id);if(!issues.length)return;
  const box=el('details');box.className='correction_results';box.append(el('summary',`이전 수정·재검증 이력 · ${issues.length}건`));
  const labels={PENDING:'재검증 대기',STILL_PRESENT:'같은 문제가 남아 있음',NOT_EVALUATED:'검토·검사 입력 확인 필요',NOT_REPORTED:'새 검사에서 이 문제가 다시 발견되지 않음'};
  for(const issue of issues){const item=el('p',`시점 ${issue.ordinal+1} · ${issue.title} → ${dirty?'재검증 대기':labels[issue.status]}`);item.dataset.correctionCode=issue.code;item.dataset.correctionStatus=dirty?'PENDING':issue.status;box.append(item);}
  box.append(el('small','선택한 시점의 이전 검사와 재검증을 비교한 이력입니다. 현재 남아 있는 문제는 위의 검사 결과에서 확인하세요.'));
  $('seq_common_review').append(box);
 }
 async function render(){
  const request=++token,m=state.moment;if(cocReviewMoment!==m?.id){cocReviewPath=null;editorSource=null;cocReviewMoment=m?.id;rearmed.clear();}coc=project(data('sequence_coc'),'sequence_coc');bundle=project(data('sequence_constraints'),'sequence_constraints');dirty=false;view=null;
  reviewDraft=null;
  if(m&&!applyingReview){try{reviewDraft=JSON.parse(sessionStorage.getItem(draftKey())||'null');}catch(e){reviewDraft=null;}if(reviewDraft){coc=clone(reviewDraft.values.sequence_coc);bundle=clone(reviewDraft.values.sequence_constraints);if(draftChanged())showStage(4);}}
  if(m&&!m.components.sequence_coc)coc.evidence_refs=[m.frame.frame_id];
  $('seq_explanation').value=displayProse(coc.explanation);$('seq_original_explanation').textContent=displayProse(original('sequence_coc')?.explanation||'아직 생성된 CoC가 없습니다.');
  $('seq_explanation').dataset.path='explanation';cocSummary();cocFields();
  $('seq_accept_coc').checked=!!data('sequence_coc').accepted_unchanged;$('seq_accept_constraints').checked=!!data('sequence_constraints').accepted_unchanged;
  cards();reviewEditor();renderDerived();controls();if(!m)return;
   const loaded=await api(`/extractions/${m.extraction_id}/sequence`);if(request!==token||state.moment?.id!==m.id)return;view=loaded;refreshForms();renderDerived();controls();resumePending();
 }
 function resumePending(){
  const stage=Object.values(view?.stages||{}).find(s=>['QUEUED','RUNNING'].includes(s.job_status));
  if(!stage||state.busy||resumedJob===stage.job_id)return;
  resumedJob=stage.job_id;
  Promise.resolve().then(()=>work(async()=>{await pollJob(stage.job_id);})).catch(error).finally(()=>{resumedJob=null;});
 }
 for(const [id,kind] of [['seq_generate_coc','SEQ_COC'],['seq_generate_constraints','SEQ_CONSTRAINTS']])bind(id,()=>work(async()=>{if(kind==='SEQ_COC')cocReviewPath=null;const j=await api(`/moments/${state.moment.id}/jobs`,'POST',{revision:state.moment.revision,type:kind});await pollJob(j.job_id);}));
 for(const [suffix,next] of [['coc',2],['constraints',3]])bind('seq_approve_'+suffix,()=>work(async()=>{await approveReviewed('sequence_'+suffix);showStage(next);controls();}));
 bind('seq_resume',()=>work(async()=>{if(draftChanged()){showStage(4);controls();return;}if(!approved('sequence_coc'))showStage(1);else if(!approved('sequence_constraints'))showStage(2);else await rerunDerived();}));
 bind('seq_approve_constraints_recheck',()=>work(async()=>{await approveReviewed('sequence_constraints',true);await rerunDerived();}));
 bind('seq_open_pending_constraints',async()=>{let index=pendingFactIndex();if(index<0&&bundle.facts?.length)index=0;const key=Array.isArray(bundle.new_definitions)?'new_definitions':'constraints';await openBatchSource({moment_id:state.moment.id,component:'sequence_constraints',path:index>=0?`/facts/${index}`:`/${key}${bundle[key]?.length?'/0':''}`,value:clone(index>=0?bundle.facts[index]:bundle[key]?.[0]||[])});});
 for(const [id,path] of [['seq_generate_eblc','sequence-eblc'],['seq_check','sequence-verify'],['seq_generate_cnl','sequence-cnl']])bind(id,()=>work(async()=>{const j=await api(`/extractions/${state.moment.extraction_id}/${path}`,'POST',{});await pollJob(j.job_id);await render();}));
 bind('seq_apply_review',()=>work(()=>applyReviewDraft(false)));
 bind('seq_apply_verify',()=>work(()=>applyReviewDraft(true)));
 bind('seq_recheck_saved',()=>work(()=>rerunDerived()));
 bind('seq_discard_review',async()=>{if(state.busy)return;sessionStorage.removeItem(draftKey());reviewDraft=null;editorSource=null;await render();showStage(4);$('seq_batch_feedback').textContent='수정 초안을 취소했습니다. 저장본은 바뀌지 않았습니다.';});
 bind('seq_next_verify',()=>{showStage(4);controls();});bind('seq_next_cnl',()=>{showStage(5);controls();});
 bind('seq_back_to_coc',()=>{showStage(1);controls();});
 for(const [id,resetId,kind] of repeatButtons)bind(resetId,()=>{if(state.busy||state.navigationPending!==null)return;const done=completedRun(kind);if(done){rearmed.set(id,done);controls();$(id).focus();}});
 document.addEventListener('studio:session',()=>{cocReviewPath=null;editorSource=null;cocReviewMoment=null;reviewDraft=null;rearmed.clear();});
 document.addEventListener('studio:moment',()=>{rendering=render();rendering.catch(error);});document.addEventListener('studio:committed',()=>committed().catch(error));document.addEventListener('studio:saved',controls);for(const b of $('pipeline_nav').children)b.addEventListener('click',()=>{if(b.dataset.stage==='1'){cocReviewPath=null;refreshForms();}else{renderDerived();controls();}});controls();
})();
