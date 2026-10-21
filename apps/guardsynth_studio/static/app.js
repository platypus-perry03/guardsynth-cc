"use strict";
const API = "/api/studio/v1";
const $ = id => document.getElementById(id);
const state = {csrf:null, moment:null, moments:[], extraction:null, videos:[], busy:false, capabilities:null, video:null, extractions:[],stage:1, navigation:0, navigationPending:null};
// Resizing is local presentation state; it does not save or approve a CoC.
const reviewWorkspace=document.querySelector(".review_workspace"),reviewDivider=$("review_divider");
const wideReview=matchMedia("(min-width:1181px)");
let viewerShare=.375,reviewDrag=null;
function layoutReview(){
  if(!wideReview.matches)return;
  const available=reviewWorkspace.getBoundingClientRect().width-18;
  if(available<700)return;
  const width=Math.min(available-420,Math.max(280,available*viewerShare));
  reviewWorkspace.style.setProperty("--viewer-width",`${width}px`);
  reviewDivider.setAttribute("aria-valuemin",String(Math.round(280/available*100)));
  reviewDivider.setAttribute("aria-valuemax",String(Math.round((available-420)/available*100)));
  reviewDivider.setAttribute("aria-valuenow",String(Math.round(width/available*100)));
  reviewDivider.setAttribute("aria-valuetext",`영상 너비 ${Math.round(width)} 픽셀`);
}
function resizeReview(width){
  const available=reviewWorkspace.getBoundingClientRect().width-18;
  if(!wideReview.matches||available<700)return;
  viewerShare=Math.min(available-420,Math.max(280,width))/available;
  layoutReview();
}
function finishReviewResize(){
  const drag=reviewDrag;reviewDrag=null;
  document.body.classList.remove("review_resizing");
  if(drag&&reviewDivider.hasPointerCapture(drag.id))reviewDivider.releasePointerCapture(drag.id);
}
reviewDivider.addEventListener("pointerdown",e=>{
  if(e.button!==0||!wideReview.matches)return;
  e.preventDefault();reviewDivider.focus({preventScroll:true});
  reviewDrag={id:e.pointerId,offset:e.clientX-$("viewer").getBoundingClientRect().right};
  reviewDivider.setPointerCapture(e.pointerId);document.body.classList.add("review_resizing");
});
reviewDivider.addEventListener("pointermove",e=>{
  if(reviewDrag?.id===e.pointerId)resizeReview(e.clientX-reviewWorkspace.getBoundingClientRect().left-reviewDrag.offset);
});
for(const event of ["pointerup","pointercancel","lostpointercapture"])reviewDivider.addEventListener(event,finishReviewResize);
reviewDivider.addEventListener("keydown",e=>{
  if(!wideReview.matches)return;
  const width=$("viewer").getBoundingClientRect().width;
  const target={ArrowLeft:width-20,ArrowRight:width+20,Home:280,End:reviewWorkspace.getBoundingClientRect().width-438}[e.key];
  if(target===undefined)return;
  e.preventDefault();resizeReview(target);
});
new ResizeObserver(layoutReview).observe(reviewWorkspace);
wideReview.addEventListener("change",()=>{finishReviewResize();layoutReview();});
const clone=v=>JSON.parse(JSON.stringify(v));
const key=()=>crypto.randomUUID();
function error(e){$('error').textContent=e.message||String(e);}
function clearError(){$('error').textContent='';}
function button(text,fn){const b=document.createElement('button');b.textContent=text;b.onclick=()=>Promise.resolve().then(fn).catch(error);return b;}
function bind(id,fn){$(id).onclick=()=>Promise.resolve().then(fn).catch(error);}
async function api(path, method="GET", body, idempotency=key()){
  const requestCsrf=state.csrf;
  const headers={};
  if(method!=="GET"){headers["X-CSRF-Token"]=state.csrf;headers["Idempotency-Key"]=idempotency;}
  if(body && !(body instanceof FormData)){headers["Content-Type"]="application/json";if(method==="PATCH")headers["If-Match"]=String(body.revision);body=JSON.stringify(body);}
  const r=await fetch(API+path,{method,headers,body,credentials:"same-origin"});
  const value=await r.json();if(!r.ok){
    if(r.status===401&&path!=='/login'&&state.csrf===requestCsrf){state.csrf=null;for(const dialog of document.querySelectorAll('dialog[open]'))dialog.close();$('workspace').hidden=true;$('login').hidden=false;$('logout').hidden=true;}
    const e=new Error(`${r.status}: ${value.message}`);e.status=r.status;throw e;
  }return value;
}
let outbox;
const dbReady = new Promise((resolve,reject)=>{const r=indexedDB.open("guardsynth-studio-outbox",1);r.onupgradeneeded=()=>r.result.createObjectStore("edits",{keyPath:"id"});r.onsuccess=()=>{outbox=r.result;resolve();};r.onerror=()=>reject(r.error);});
async function dbOp(method,value){await dbReady;return new Promise((resolve,reject)=>{const tx=outbox.transaction("edits",method==="getAll"?"readonly":"readwrite");const s=tx.objectStore("edits");const r=method==="getAll"?s.getAll():s[method](value);tx.oncomplete=()=>resolve(r.result);tx.onerror=()=>reject(tx.error);});}
let timer, flushing=null, queuing=Promise.resolve(), lastQueued=0;
async function draftNotice(){
  const rows=(await dbOp('getAll')).filter(r=>r.deferred);
  $('drafts_notice').hidden=!rows.length;
  $('drafts_message').textContent=`이전 임시 수정 ${rows.length}건을 보관하고 있습니다. 현재 저장본을 표시하며, 임시 수정은 자동으로 반영하지 않습니다.`;
  return rows.sort((a,b)=>a.created-b.created);
}
async function deferDrafts(){
  clearTimeout(timer);await queuing;
  for(const row of await dbOp('getAll')){row.deferred=true;await dbOp('put',row);}
  await draftNotice();
}
function showConflict(row,current){
  const payload=current.components[row.kind]?.payload||{};
  const selected=Object.fromEntries(Object.keys(row.payload).map(k=>[k,payload[k]]));
  state.conflict={row,current};
  $('conflict_diff').textContent=JSON.stringify({'시점':current.ordinal+1,'항목':({sequence_coc:'CoC',sequence_constraints:'제약 사항'})[row.kind]||'초안','이전 임시 수정':row.payload,'현재 저장본':selected},null,2);
  if(!$('conflict').open)$('conflict').showModal();
}
async function queue(kind,payload){
  if(!state.moment)return;
  const row={id:key(),moment_id:state.moment.id,revision:state.moment.revision,kind,payload:clone(payload),created:lastQueued=Math.max(Date.now(),lastQueued+1),sent:false};
  queuing=queuing.catch(()=>{}).then(async()=>{
    // A rejected draft was never committed; its replacement may use a new key.
    for(const old of await dbOp("getAll"))if(!old.deferred&&old.rejected&&old.moment_id===row.moment_id&&old.kind===kind)await dbOp("delete",old.id);
    if(state.moment?.id===row.moment_id)row.revision=state.moment.revision;
    await dbOp("put",row);
    $("save_state").textContent="임시 저장 중";
    clearTimeout(timer);timer=setTimeout(()=>flush().catch(error),500);
  });
  return queuing;
}
async function flush(){
  if(flushing)return flushing;
  flushing=(async()=>{
    let committed=false;
    while(true){
    await queuing;
    const rows=(await dbOp("getAll")).filter(r=>!r.deferred).sort((a,b)=>a.created-b.created);
    if(!rows.length)break;
    for(const row of rows){
      if(!(await dbOp("getAll")).some(x=>x.id===row.id))continue;
      row.sent=true;await dbOp("put",row);
      let result;
      try{result=await api(`/moments/${row.moment_id}`,"PATCH",{revision:row.revision,kind:row.kind,payload:row.payload},row.id);}
      catch(e){
        if(e.status===422){
          row.rejected=true;row.sent=false;await dbOp("put",row);await queuing;
          const newer=(await dbOp("getAll")).some(x=>!x.deferred&&x.moment_id===row.moment_id&&x.kind===row.kind&&x.created>row.created);
          if(newer){await dbOp("delete",row.id);continue;}
        }
        if(e.status===409){const current=await api(`/moments/${row.moment_id}`);showConflict(row,current);}
        throw e;
      }
      await dbOp("delete",row.id);
      committed=true;
      // Only advance unsent edits after an acknowledged write from this outbox.
      for(const next of await dbOp("getAll"))if(next.moment_id===row.moment_id && !next.sent&&!next.deferred){next.revision=result.revision;await dbOp("put",next);const local=rows.find(r=>r.id===next.id);if(local)local.revision=result.revision;}
      if(state.moment?.id===row.moment_id){state.moment={...state.moment,...result};renderControls();}
    }
    }
    $("save_state").textContent="저장됨";
    await draftNotice();
    if($("error").textContent.startsWith("422:"))$("error").textContent="";
    if(committed)document.dispatchEvent(new CustomEvent('studio:committed'));
  })().catch(e=>{$("save_state").textContent="저장 실패 · 초안 유지 (409는 최신본과 비교 필요)";throw e;}).finally(()=>{flushing=null;});
  return flushing;
}
function data(kind){return state.moment?.components[kind]?.payload || {};}
async function approve(kind,decision){await flush();const m=await api(`/moments/${state.moment.id}`),c=m.components[kind];if(!c)throw Error("먼저 초안을 저장하세요");await api("/approvals","POST",{items:[{moment_id:m.id,revision:m.revision,stage:kind,component_id:c.id,dependency_digest:c.dependency_digest,decision}]});await loadMoment(m.id);}

function renderVehicleState(value){
  const host=$("vehicle_state");host.replaceChildren();
  const title=document.createElement("h3");title.textContent="현재 시점 CAN";host.append(title);
  const row=value?.frames?.at(-1),sample=row?.sample;
  if(!sample){const p=document.createElement("p");p.textContent=value?"현재 시점 이전 600 ms 이내의 측정값 없음":"연결된 CAN 없음 · 영상만 검토";host.append(p);return;}
  const table=document.createElement("table");
  for(const [name,field,unit] of [["속도","vehicle_speed_kmh","km/h"],["브레이크 압력","brake_pressure_bar","bar"],["스로틀","throttle_permille","‰"],["조향각","steering_deg","°"]]){
    const tr=document.createElement("tr"),th=document.createElement("th"),td=document.createElement("td");th.textContent=name;td.textContent=`${Number(sample[field].toFixed(3))} ${unit}`;td.title=`원자료: ${sample[field]} ${unit}`;tr.append(th,td);table.append(tr);
  }
  const note=document.createElement("p");note.textContent=`${value.scene_id} · 측정 ${(sample.timestamp_us/1e6).toFixed(3)}s · 영상 시점과 차이 ${(row.age_us/1000).toFixed(1)} ms. 실측 제어값이며 운전자 의도는 별도 검토하세요.`;host.append(table,note);
}
function timelineLabel(ordinal){const m=state.moments[ordinal];return m?`시점 ${ordinal+1} / ${state.moments.length} · ${(m.t0_us/1e6).toFixed(3)}s`:"추출을 선택하세요";}
function renderThumbnailStrip(m){
  const host=$("strip"),sameExtraction=host.dataset.extraction===m.extraction_id;
  const previousOrdinal=Number(host.dataset.ordinal),direction=Math.sign(m.ordinal-previousOrdinal);
  const existing=new Map(sameExtraction?[...host.children].map(b=>[Number(b.dataset.ordinal),b]):[]);
  const positions=new Map([...existing].map(([ordinal,b])=>[ordinal,b.getBoundingClientRect().left]));
  const scene=m.vehicle_state?.scene_id || state.videos.find(v=>v.id===state.video)?.name || "장면 이름 없음";
  const buttons=m.frames.map(f=>{
    let b=existing.get(f.ordinal);
    if(!b){
      b=button("",()=>selectOrdinal(f.ordinal));b.dataset.ordinal=String(f.ordinal);
      const img=document.createElement("img");img.src=API+"/assets/"+f.asset_id;img.alt=`frame ${f.ordinal+1}`;
      const name=document.createElement("span");name.className="thumb_scene";
      const time=document.createElement("span");time.className="thumb_time";time.textContent=`${(f.timestamp_us/1e6).toFixed(3)}s`;b.append(img,name,time);
    }
    b.querySelector(".thumb_scene").textContent=scene;b.title=`${scene} · 시점 ${f.ordinal+1} · ${(f.timestamp_us/1e6).toFixed(3)}s`;b.setAttribute("aria-label",b.title);
    if(f.ordinal===m.ordinal)b.setAttribute("aria-current","true");else b.removeAttribute("aria-current");
    return b;
  });
  host.replaceChildren(...buttons);host.dataset.ordinal=String(m.ordinal);host.dataset.extraction=m.extraction_id;
  if(sameExtraction && Math.abs(m.ordinal-previousOrdinal)===1 && !matchMedia("(prefers-reduced-motion: reduce)").matches){
    for(const b of buttons){const rect=b.getBoundingClientRect(),previous=positions.get(Number(b.dataset.ordinal));const offset=previous===undefined?direction*(rect.width+4):previous-rect.left;if(offset)b.animate([{transform:`translateX(${offset}px)`},{transform:"translateX(0)"}],{duration:180,easing:"ease-out"});}
  }
}
function renderTimeline(){const slider=$("timeline");slider.max=String(Math.max(0,state.moments.length-1));slider.value=String(state.moment?.ordinal || 0);$("timeline_position").textContent=timelineLabel(Number(slider.value));slider.setAttribute("aria-valuetext",$("timeline_position").textContent);}
$("timeline").oninput=()=>{const value=timelineLabel(Number($("timeline").value));$("timeline_position").textContent="이동할 "+value;$("timeline").setAttribute("aria-valuetext",value);};
$("timeline").onchange=()=>selectOrdinal(Number($("timeline").value)).catch(e=>{renderTimeline();error(e);});
function updateActions(){
  document.dispatchEvent(new CustomEvent('studio:saved'));
  const busy=state.busy || state.navigationPending!==null;
  $('timeline').disabled=!state.moment||busy;
  $('previous').disabled=!state.moment||busy||state.moment.ordinal===0;
  $('next').disabled=!state.moment||busy||state.moment.ordinal===state.moments.length-1;
  $('video_select').disabled=busy;$('extraction_select').disabled=busy;$('refresh').disabled=busy;
  $('enlarge').disabled=!state.moment;
}
function renderControls(){document.dispatchEvent(new CustomEvent('studio:saved'));}
function showStage(stage){state.stage=stage;for(const panel of document.querySelectorAll('.pipeline_step'))panel.hidden=Number(panel.dataset.step)!==stage;for(const b of $('pipeline_nav').children)b.setAttribute('aria-current',Number(b.dataset.stage)===stage?'step':'false');}
for(const b of $('pipeline_nav').children)b.onclick=()=>showStage(Number(b.dataset.stage));
async function loadMoment(id,preserveNavigation=false){
  if(!id)return;
  if(!preserveNavigation)await flush();
  if(preserveNavigation&&state.navigationPending!==null)return;
  const navigation=++state.navigation;state.navigationPending=navigation;
  try{
    const m=await api(`/moments/${id}`);
    if(navigation!==state.navigation)return;
    state.moment=m;
    $('timestamp').textContent=`시점 ${m.ordinal+1} · ${(m.t0_us/1e6).toFixed(3)}초`;
    renderThumbnailStrip(m);renderTimeline();renderVehicleState(m.vehicle_state);
    $('current_frame').src=API+'/assets/'+m.frame.asset_id;
    for(const b of $('moments').children)b.setAttribute('aria-current',Number(b.dataset.ordinal)===m.ordinal?'true':'false');
    localStorage.setItem('guardsynth-studio-selection',JSON.stringify({video:state.video,extraction:state.extraction,moment:m.id}));
    document.dispatchEvent(new CustomEvent('studio:moment'));
    await api(`/moments/${m.id}/exposure`,'POST',{revision:m.revision,panel:'moment_view'});
  }finally{if(state.navigationPending===navigation)state.navigationPending=null;updateActions();}
}
async function selectOrdinal(i){if(i>=0&&i<state.moments.length)await loadMoment(state.moments[i].id);}
async function refreshMoments(){
  if(!state.extraction)return;
  state.moments=(await api(`/extractions/${state.extraction}/moments`)).moments;
  $('counts').textContent=`${state.moments.length}개 시점`;$('moments').replaceChildren();
  for(const m of state.moments){const b=button(`${m.ordinal+1} · ${(m.t0_us/1e6).toFixed(3)}초`,()=>loadMoment(m.id));b.dataset.ordinal=String(m.ordinal);$('moments').append(b);}
}
function renderVideo(){
  const select=$('extraction_select');select.replaceChildren();
  const ready=state.extractions.filter(e=>e.video_id===state.video&&e.status==='READY');
  for(const [i,ex] of ready.entries()){const o=document.createElement('option');o.value=ex.id;o.textContent=`${ex.interval_s}초 간격 · ${ex.frames?.length||0}개 시점${ready.filter(e=>e.interval_s===ex.interval_s).length>1?` · 추출 ${i+1}`:''}`;select.append(o);}
  select.value=state.extraction||'';
}
async function openExtraction(id,preferredMoment){
  await flush();state.extraction=id;const ex=state.extractions.find(e=>e.id===id);if(!ex)return;
  state.video=ex.video_id;$('video_select').value=state.video;renderVideo();await refreshMoments();
  const selected=state.moments.find(m=>m.id===preferredMoment)||state.moments.find(m=>m.revision>0)||state.moments[0];
  if(selected)await loadMoment(selected.id);
}
async function refresh(){
  const r=await api('/videos');state.videos=r.videos;state.extractions=r.extractions;
  if(!state.videos.some(v=>v.id===state.video))state.video=state.videos.find(v=>v.vehicle_state_id)?.id||state.videos[0]?.id;
  const select=$('video_select');select.replaceChildren();
  for(const v of state.videos){const o=document.createElement('option');o.value=v.id;o.textContent=v.name||v.source||'영상';select.append(o);}select.value=state.video||'';
  if(!state.extractions.some(e=>e.id===state.extraction&&e.video_id===state.video))state.extraction=state.extractions.filter(e=>e.video_id===state.video&&e.status==='READY').at(-1)?.id;
  renderVideo();await refreshMoments();updateActions();
}
async function refreshCapabilities(){state.capabilities=await api('/capabilities');const c=state.capabilities,b=c.call_budget;$('provider').textContent=`${c.model||'모델 미설정'}${b?` · 호출 ${b.used}/${b.limit}`:''}`;updateActions();}
async function pollJob(id){
  for(let i=0;i<650;i++){
    const j=await api(`/jobs/${id}`);
    if(!['QUEUED','RUNNING'].includes(j.status)){
      if(j.status!=='SUCCEEDED'){
        if(state.moment)await loadMoment(state.moment.id,true);
        if(j.status==='STALE_RESULT'||j.error?.code==='PROVIDER_STALE')throw Error('입력이 바뀌어 결과를 적용하지 않았습니다. 최신 입력으로 다시 실행하세요.');
        const stage={SEQ_COC:'CoC 생성',SEQ_CONSTRAINTS:'제약 생성',SEQ_EBLC:'EBLC 생성',SEQ_VERIFY:'검증',SEQ_CNL:'CNL 생성'}[j.kind];
        const reason={PROVIDER_BUDGET:'모델 호출 한도를 모두 사용했습니다.',PROVIDER_AUTH:'모델 서비스 인증 설정을 확인하세요.',PROVIDER_KEY_MISSING:'모델 서비스 인증 키가 설정되지 않았습니다.',PROVIDER_RATE_LIMIT:'모델 서비스의 일시적인 호출 제한입니다. 잠시 후 다시 실행하세요.',PROVIDER_TIMEOUT:'모델 응답 시간이 초과되었습니다. 다시 실행할 수 있습니다.',PROVIDER_TRANSPORT:'모델 서비스 연결에 실패했습니다. 연결 상태를 확인하세요.',PROVIDER_RESPONSE_SIZE:'모델 응답이 너무 커서 적용하지 못했습니다. 다시 생성할 수 있습니다.',PROVIDER_SCHEMA:'모델이 정해진 출력 형식에 맞지 않는 결과를 만들었습니다. 다시 생성하세요.'}[j.error?.code];
        const detail=['PROVIDER_RELATION_FORMAT','PROVIDER_CURRENT_OBSERVATION'].includes(j.error?.code)?j.error.message:reason||'입력과 검토 상태를 확인한 뒤 다시 실행하세요.';
        throw Error(stage?`${stage} 작업이 완료되지 않았습니다. ${detail}`:j.error?.message||'작업이 완료되지 않았습니다. 다시 실행하세요.');
      }
      await refreshCapabilities();if(state.moment)await loadMoment(state.moment.id,true);await refresh();return j;
    }
    await new Promise(r=>setTimeout(r,500));
  }
  throw Error('작업이 아직 진행 중입니다. 잠시 후 새로고침하세요.');
}
async function activate(){
  clearError();
  for(const dialog of document.querySelectorAll('dialog[open]'))dialog.close();
  state.conflict=null;state.moment=null;showStage(1);
  $('seq_eblc_raw').open=false;document.dispatchEvent(new CustomEvent('studio:session'));
  await deferDrafts();
  await dbReady;$('login').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;
  try{const saved=JSON.parse(localStorage.getItem('guardsynth-studio-selection'));if(saved){state.video=saved.video;state.extraction=saved.extraction;state.preferredMoment=saved.moment;}}catch(e){}
  await refreshCapabilities();await flush();await refresh();if(state.extraction)await openExtraction(state.extraction,state.preferredMoment);
}
$('login_form').addEventListener('input',clearError);
$('login_form').onsubmit=async e=>{e.preventDefault();clearError();try{const r=await api('/login','POST',{actor_id:$('actor').value,secret:$('secret').value});$('secret').value='';state.csrf=r.csrf_token;state.actor=r.actor_id;await activate();}catch(e){error(e);}};
$('video_select').onchange=async()=>{try{await flush();state.video=$('video_select').value;const ex=state.extractions.filter(e=>e.video_id===state.video&&e.status==='READY').at(-1);state.moment=null;state.extraction=null;state.moments=[];renderVideo();if(ex)await openExtraction(ex.id);else{ $('timestamp').textContent='준비된 추출이 없습니다';$('current_frame').removeAttribute('src');$('strip').replaceChildren();$('moments').replaceChildren();document.dispatchEvent(new CustomEvent('studio:moment'));updateActions();}}catch(e){error(e);}};
$('extraction_select').onchange=()=>openExtraction($('extraction_select').value).catch(error);
bind('refresh',async()=>{await flush();await refreshCapabilities();await refresh();if(state.moment)await loadMoment(state.moment.id);else if(state.extraction)await openExtraction(state.extraction);});
bind('previous',()=>selectOrdinal(state.moment.ordinal-1));bind('next',()=>selectOrdinal(state.moment.ordinal+1));
bind('enlarge',()=>{$('zoom_image').src=$('current_frame').src;$('zoom').showModal();});bind('close_zoom',()=>$('zoom').close());
bind('conflict_apply',async()=>{const {row,current}=state.conflict;await dbOp('delete',row.id);const replacement={...row,id:key(),revision:current.revision,sent:false,deferred:false};await dbOp('put',replacement);for(const next of await dbOp('getAll'))if(next.moment_id===row.moment_id&&!next.sent&&!next.deferred){next.revision=current.revision;await dbOp('put',next);}$('conflict').close();await flush();if(state.extraction!==current.extraction_id)await openExtraction(current.extraction_id,row.moment_id);else await loadMoment(row.moment_id);});
bind('conflict_close',()=>$('conflict').close());
bind('drafts_review',async()=>{const row=(await draftNotice())[0];if(!row)return;const current=await api(`/moments/${row.moment_id}`);showConflict(row,current);});
bind('drafts_discard',async()=>{for(const row of await draftNotice())await dbOp('delete',row.id);await draftNotice();});
bind('logout',async()=>{await flush();await api('/logout','POST',{});$('workspace').hidden=true;$('login').hidden=false;$('logout').hidden=true;state.csrf=null;state.moment=null;for(const key of Object.keys(sessionStorage))if(key.startsWith('guardsynth:review:'))sessionStorage.removeItem(key);clearError();});
(async()=>{try{const session=await api('/session');state.csrf=session.csrf_token;state.actor=session.actor_id;await activate();}catch(e){if(e.status!==401)error(e);}})();
showStage(1);
