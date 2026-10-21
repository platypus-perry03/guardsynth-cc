import http.client
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from apps.research_portal.security import hash_secret
from apps.guardsynth_studio.server import make_server
from apps.guardsynth_studio.common import uid
from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio.store import Store
from apps.guardsynth_studio.service import Service
from .helpers import fixture
from .browser_driver import Browser


class HTTPTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store, self.service, self.ids, self.extraction, _, _ = fixture(Path(self.temp.name) / "store")
        self.auth = {"users": [{"actor_id": "reviewer", "secret_hash": hash_secret("studio-test-password"), "roles": ["REVIEWER"]}]}
        self.server = make_server(self.service, self.auth)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True);self.thread.start()
        self.port = self.server.server_port
        self.cookie = self.csrf = None

    def tearDown(self):
        self.doCleanups()
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.store.close();self.temp.cleanup()

    def request(self, path, method="GET", body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdr = {"Content-Type": "application/json"}
        if self.cookie: hdr["Cookie"] = self.cookie
        if self.csrf: hdr["X-CSRF-Token"] = self.csrf
        if method != "GET": hdr["Idempotency-Key"] = uid()
        hdr.update(headers or {})
        connection.request(method, path, json.dumps(body).encode() if body is not None else None, hdr)
        response = connection.getresponse();data=response.read()
        result = (response.status, dict(response.getheaders()), data)
        connection.close();return result

    def login(self):
        status, headers, body = self.request("/api/studio/v1/login", "POST", {"actor_id": "reviewer", "secret": "studio-test-password"})
        self.assertEqual(status,200)
        self.cookie=headers["Set-Cookie"].split(";",1)[0]
        self.csrf=json.loads(body)["csrf_token"]

    def test_auth_csrf_path_disabled_provider_and_if_match(self):
        prefix="/api/studio/v1"
        self.assertEqual(self.request(prefix+"/videos")[0],401)
        self.login()
        status, headers, body=self.request(prefix+"/capabilities")
        self.assertEqual(status,200);self.assertEqual(json.loads(body)["provider_mode"],"DISABLED")
        self.assertEqual(self.request(prefix+"/videos",headers={"Origin":"https://outside.invalid"})[0],403)
        path=prefix+"/moments/"+self.ids[0]
        data={"revision":0,"kind":"coc","payload":{"edited_text":"<script>window.pwned=true</script>"}}
        self.assertEqual(self.request(path,"PATCH",data,{"X-CSRF-Token":"bad","If-Match":"0"})[0],403)
        self.assertEqual(self.request(path,"PATCH",data)[0],409)
        self.assertEqual(self.request(path,"PATCH",data,{"If-Match":"0"})[0],200)
        self.assertEqual(self.request(path,"PATCH",data,{"If-Match":"0"})[0],409)
        self.assertEqual(self.request(path+"/jobs","POST",{"revision":1,"type":"COC"})[0],503)
        for malicious in ("..", "%2e%2e%2fetc%2fpasswd", "%252e%252e%252fetc"):
            self.assertIn(self.request(prefix+"/assets/"+malicious)[0],(403,404))
        self.assertNotIn(b"secret_hash",body)
        self.assertIn("Content-Security-Policy",headers)

    def test_manual_is_read_only_and_does_not_expose_workspace(self):
        # A missing static route or an over-broad unauthenticated route is a regression.
        status, headers, body = self.request("/manual.html")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn("Content-Security-Policy", headers)
        from html.parser import HTMLParser
        class Page(HTMLParser):
            def __init__(self):
                super().__init__(); self.ids=set(); self.anchors=[]; self.scripts=[]
            def handle_starttag(self, tag, attrs):
                attrs=dict(attrs)
                if "id" in attrs: self.ids.add(attrs["id"])
                if tag=="a": self.anchors.append(attrs)
                if tag=="script": self.scripts.append(attrs)
        manual=Page(); manual.feed(body.decode())
        self.assertFalse(manual.scripts)
        for link in manual.anchors:
            if link.get("href", "").startswith("#"):
                self.assertIn(link["href"][1:], manual.ids)
        workspace=Page(); workspace.feed(self.request("/")[2].decode())
        links=[a for a in workspace.anchors if a.get("href", "").startswith("/manual.html")]
        self.assertTrue(links, "Workspace must expose the help page")
        for link in links:
            self.assertEqual(link.get("target"), "_blank")
            self.assertIn("noopener", link.get("rel", "").split())
            if "#" in link["href"]: self.assertIn(link["href"].split("#",1)[1], manual.ids)
        self.assertEqual(self.request("/api/studio/v1/videos")[0],401)
        self.assertNotEqual(self.request("/manual.html", "POST", {})[0],200)
        self.assertNotEqual(self.request("/../auth.json")[0],200)
        self.assertEqual(self.store.objects("job"),[])







    def test_http_supplied_null_can_rejects_entire_pair(self):
        self.login()
        metadata = {"name": "null-pair.mp4", "source": "synthetic", "license": "test", "permission": True}
        boundary = "studio-test-boundary"
        fields = [("file", b"synthetic-video"), ("metadata", json.dumps(metadata).encode()), ("vehicle_state", b"null")]
        body = b"".join((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + value + b"\r\n") for name, value in fields) + f"--{boundary}--\r\n".encode()
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request("POST", "/api/studio/v1/videos", body, {"Content-Type": f"multipart/form-data; boundary={boundary}", "Cookie": self.cookie, "X-CSRF-Token": self.csrf, "Idempotency-Key": uid()})
            response = connection.getresponse();response.read()
            self.assertEqual(response.status, 422)
        finally:
            connection.close()
        self.assertEqual(len(self.store.objects("video")), 1)
        self.assertEqual(self.store.objects("job"), [])










    def test_http_server_restart_preserves_committed_edit(self):
        self.login()
        path = "/api/studio/v1/moments/" + self.ids[0]
        self.assertEqual(self.request(path,"PATCH",{"revision":0,"kind":"coc","payload":{"edited_text":"server restart"}},{"If-Match":"0"})[0],200)
        self.server.shutdown();self.server.server_close();self.thread.join();self.store.close()
        self.store = Store(Path(self.temp.name)/"store")
        self.service = Service(self.store)
        self.server = make_server(self.service,self.auth,self.port)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.assertEqual(self.request(path)[0],401)
        self.cookie=self.csrf=None;self.login()
        status,_,body=self.request(path)
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["components"]["coc"]["payload"]["edited_text"],"server restart")











    def browser_login(self):
        browser=Browser(self.temp.name,f'http://127.0.0.1:{self.port}/')
        self.addCleanup(browser.close)
        browser.evaluate("$('actor').value='reviewer';$('secret').value='studio-test-password';$('login_form').requestSubmit(); true")
        browser.wait("!$('workspace').hidden && state.extractions.length>0")
        browser.evaluate('openExtraction('+json.dumps(self.extraction)+').then(()=>true)')
        return browser

    def test_browser_minimal_five_stage_cycle_accepts_without_manual_options(self):
        from .test_sequence import scene,condition
        class Provider:
            mode='MOCK';model='test-only'
            def generate(self,kind,frames,prompt,schema,limits):
                data=scene(0)['coc'] if kind=='SEQ_COC' else {'constraints':[condition(source_refs=[])]}
                if kind=='SEQ_COC': data['evidence_refs']=[frames[-1]['frame_id']]
                else: data['constraints'][0]['evidence_refs']=[frames[-1]['frame_id']]
                return {'parsed_candidate':data,'raw_output':json.dumps(data),'model_version':'test-only','provider_request_id':uid()}
        self.service.provider=Provider()
        browser=self.browser_login()
        self.assertEqual(browser.evaluate("document.querySelectorAll('.pipeline_step').length"),5)
        self.assertFalse(browser.evaluate("!!$('legacy_coc') || !!$('follow_up') || !!$('seq_catalog') || !!$('json_editor')"))
        self.assertEqual(browser.evaluate("document.querySelectorAll('#sequence_review select').length"),0)
        browser.evaluate("$('seq_generate_coc').click();$('seq_generate_coc').click();true")
        browser.wait('state.busy && $("seq_generate_coc").disabled')
        end=time.monotonic()+5
        while not self.store.objects('job') and time.monotonic()<end:time.sleep(.05)
        self.assertEqual(len(self.store.objects('job')),1)
        Worker(self.service).run_once()
        browser.wait('!state.busy && $("seq_explanation").value.length>0')
        self.assertTrue(browser.evaluate("$('seq_approve_coc').disabled"))
        browser.evaluate("$('seq_accept_coc').click();true")
        browser.wait('!$("seq_approve_coc").disabled')
        browser.evaluate("$('seq_approve_coc').click();true")
        browser.wait('!state.busy && state.stage===2 && !$("seq_generate_constraints").disabled')
        browser.evaluate("$('seq_generate_constraints').click();true")
        end=time.monotonic()+5
        while len(self.store.objects('job'))<2 and time.monotonic()<end:time.sleep(.05)
        Worker(self.service).run_once()
        try: browser.wait('!state.busy && !!document.querySelector(".sequence_condition textarea")')
        except AssertionError:
            self.fail(json.dumps({"ui":browser.evaluate("({error:$('error').textContent,busy:state.busy,components:Object.keys(state.moment.components),stage:state.stage})"),"jobs":[{k:j.get(k) for k in ('kind','status','error')} for j in self.store.objects('job')]},ensure_ascii=False))
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"constraints[0].condition_class\"]').options.length"),8)
        self.assertEqual(browser.evaluate("document.querySelector('[data-path=\"constraints[0].condition_class\"]').value"),'')
        original_text=browser.evaluate("document.querySelector('.sequence_condition textarea').value")
        browser.evaluate("(()=>{const e=document.querySelector('.sequence_condition textarea');e.value='';e.dispatchEvent(new Event('input',{bubbles:true}));return flush().catch(()=>true);})()")
        browser.evaluate("(()=>{const e=document.querySelector('.sequence_condition textarea');e.value='고친 제약 설명';e.dispatchEvent(new Event('input',{bubbles:true}));return flush().catch(()=>true);})()")
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_constraints']['payload']['constraints'][0]['description'],'고친 제약 설명')
        browser.evaluate("(()=>{const e=document.querySelector('.sequence_condition textarea');e.value="+json.dumps(original_text)+";e.dispatchEvent(new Event('input',{bubbles:true}));return flush().then(()=>true);})()")
        browser.evaluate("$('seq_accept_constraints').click();true")
        browser.wait('!$("seq_approve_constraints").disabled')
        browser.evaluate("$('seq_approve_constraints').click();true")
        browser.wait('!state.busy && state.stage===3 && !$("seq_generate_eblc").disabled')
        for button,stage in [('seq_generate_eblc',3),('seq_check',4),('seq_generate_cnl',5)]:
            if stage>3: browser.evaluate('showStage('+str(stage)+');true')
            browser.wait('!$("'+button+'").disabled')
            count=len(self.store.objects('job'))
            browser.evaluate('$("'+button+'").click();true')
            end=time.monotonic()+5
            while len(self.store.objects('job'))==count and time.monotonic()<end:time.sleep(.05)
            Worker(self.service).run_once()
            browser.wait('!state.busy')
        self.assertIn('추가 확인',browser.evaluate("$('seq_cnl_verification_text').textContent"))
        self.assertNotIn('검증 상태:',browser.evaluate("$('seq_cnl_text').textContent"))
        self.assertEqual([j['kind'] for j in self.store.objects('job')],['SEQ_COC','SEQ_CONSTRAINTS','SEQ_EBLC','SEQ_VERIFY','SEQ_CNL'])
        browser.evaluate("showStage(1);$('seq_explanation').value='작성자 수정';$('seq_explanation').dispatchEvent(new Event('input',{bubbles:true}));flush().then(()=>true)")
        self.assertFalse(browser.evaluate("$('seq_accept_coc').checked"))
        browser.evaluate('loadMoment(state.moment.id).then(()=>true)')
        browser.wait('$("seq_generate_cnl").disabled && $("seq_check").disabled')
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_coc']['payload']['original_candidate']['explanation'],'보행자 때문에 대기함')
        self.assertFalse(browser.evaluate("$('error').textContent.length>0"))

    def test_browser_causal_thumbnail_queue_navigation_and_divider_preserve_edit(self):
        browser=self.browser_login()
        width=browser.evaluate('$("strip").children[0].getBoundingClientRect().width')
        browser.evaluate('selectOrdinal(6).then(()=>true)')
        self.assertEqual(browser.evaluate('$("strip").children.length'),7)
        self.assertAlmostEqual(width,browser.evaluate('$("strip").children[0].getBoundingClientRect().width'),delta=2)
        browser.evaluate("$('seq_explanation').value='<script>window.pwned=true</script>'; $('seq_explanation').dispatchEvent(new Event('input',{bubbles:true}));flush().then(()=>true)")
        browser.call('Emulation.setDeviceMetricsOverride',{'width':1600,'height':1100,'deviceScaleFactor':1,'mobile':False})
        before=browser.evaluate('$("viewer").getBoundingClientRect().width')
        browser.evaluate("$('review_divider').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));true")
        self.assertGreater(browser.evaluate('$("viewer").getBoundingClientRect().width'),before)
        browser.evaluate('selectOrdinal(9).then(()=>selectOrdinal(6)).then(()=>true)')
        self.assertEqual(browser.evaluate('$("seq_explanation").value'),'<script>window.pwned=true</script>')
        self.assertFalse(browser.evaluate('!!window.pwned'))
        browser.evaluate("$('timeline').value='2';$('timeline').dispatchEvent(new Event('change'));true")
        browser.wait('state.moment.ordinal===2')
        self.assertEqual(browser.evaluate('$("strip").children.length'),3)
        self.assertFalse(browser.evaluate('$("error").textContent.length>0'))

    def test_browser_selected_extraction_is_named_by_interval_and_frame_count(self):
        browser=self.browser_login()
        text=browser.evaluate('$("extraction_select").selectedOptions[0].textContent')
        self.assertIn('10',text)
        self.assertEqual(browser.evaluate('document.querySelectorAll("#sequence_review input:not([type=checkbox])").length'),0)
        self.assertEqual(browser.evaluate('document.querySelectorAll("#sequence_review textarea").length'),1)
