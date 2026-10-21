import sys,json,time,resource
from apps.guardsynth_studio.jobs import child
case=json.load(sys.stdin)
t=time.perf_counter()
try:
    result=child('SEQ_CHECK',case['request'])
    state={'execution':'COMPLETED','verdict':result['status'],'scene_count':len(result['scenes']),
           'last_condition_queries':result['scenes'][-1]['verification']['condition_checks']['query_count'],
           'response_bytes':len(json.dumps(result,ensure_ascii=False).encode())}
except Exception as exc:
    state={'execution':'TIMED_OUT' if type(exc).__name__=='TimeoutExpired' else 'FAILED','error_type':type(exc).__name__,'error':str(exc)[:300]}
r=resource.getrusage(resource.RUSAGE_CHILDREN)
state.update(case_id=case['case_id'],repeat=case['repeat'],wall_s=round(time.perf_counter()-t,6),
             child_cpu_s=round(r.ru_utime+r.ru_stime,6),child_max_rss_mib=round(r.ru_maxrss/1024,3),
             measure_process_max_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,3))
print(json.dumps(state,ensure_ascii=False))
