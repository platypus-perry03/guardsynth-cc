"""Stale-cookie login recovery and error lifecycle in the real browser."""
import threading
import unittest

from apps.guardsynth_studio.server import make_server
from . import test_http_browser as http
from .browser_driver import Browser


class LoginRecoveryTest(unittest.TestCase):
    setUp=http.HTTPTest.setUp
    tearDown=http.HTTPTest.tearDown
    request=http.HTTPTest.request
    login=http.HTTPTest.login
    browser_login=http.HTTPTest.browser_login

    def restart(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server=make_server(self.service,self.auth,self.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def test_stale_cookie_requires_login_but_security_failures_remain_rejected(self):
        self.login();self.restart()
        status,_,body=self.request('/api/studio/v1/session')
        self.assertEqual(status,401);self.assertIn('다시 로그인',body.decode())
        self.assertEqual(self.request('/api/studio/v1/session',headers={'Origin':'https://outside.invalid'})[0],403)
        self.login()
        self.assertEqual(self.request('/api/studio/v1/logout','POST',{},headers={'X-CSRF-Token':'wrong'})[0],403)
        self.assertEqual(self.request('/api/studio/v1/session')[0],200)

    def test_reload_after_restart_shows_clean_login_and_success_clears_old_error(self):
        b=self.browser_login();self.restart();b.call('Page.reload')
        b.wait("document.readyState==='complete' && !$('login').hidden && !$('workspace').checkVisibility()")
        b.evaluate("api('/session').catch(()=>true)")
        self.assertEqual(b.evaluate("$('error').textContent"),'')
        b.evaluate("$('error').textContent='403: Session, origin or route rejected';$('actor').value='reviewer';$('secret').value='studio-test-password';$('login_form').requestSubmit();true")
        b.wait("!$('workspace').hidden && !!state.moment")
        self.assertEqual(b.evaluate("$('error').textContent"),'')
        b.evaluate("$('error').textContent='이전 오류';$('logout').click();true")
        b.wait("!$('login').hidden && $('workspace').hidden")
        self.assertEqual(b.evaluate("$('error').textContent"),'')

    def test_failed_login_clears_on_input_and_on_new_attempt(self):
        b=Browser(self.temp.name,f'http://127.0.0.1:{self.port}/');self.addCleanup(b.close)
        b.evaluate("$('actor').value='reviewer';$('secret').value='wrong';$('login_form').requestSubmit();true")
        b.wait("$('error').textContent.startsWith('401:')")
        b.evaluate("$('secret').value='studio-test-password';$('secret').dispatchEvent(new Event('input',{bubbles:true}));true")
        self.assertEqual(b.evaluate("$('error').textContent"),'')
        b.evaluate("$('error').textContent='403: Session, origin or route rejected';const attempt=$('login_form').onsubmit({preventDefault(){}});window.errorAtLoginStart=$('error').textContent;attempt.then(()=>true)")
        self.assertEqual(b.evaluate('window.errorAtLoginStart'),'')
        b.wait("!$('workspace').hidden && !!state.moment")
        self.assertEqual(b.evaluate("$('error').textContent"),'')

    def test_expired_workspace_returns_to_login_and_keeps_unsent_drafts(self):
        b=self.browser_login()
        b.wait("!!state.moment && state.navigationPending===null")
        b.evaluate("dbOp('put',{id:'unsent-login-test',moment_id:state.moment.id,revision:state.moment.revision,kind:'sequence_coc',payload:{explanation:'임시 초안'},created:1,sent:false}).then(()=>true)")
        self.restart();b.evaluate("api('/capabilities').catch(error).then(()=>true)")
        self.assertTrue(b.evaluate("!$('login').hidden && $('workspace').hidden && state.csrf===null"))
        self.assertEqual(b.evaluate("dbOp('getAll').then(rows=>rows.map(r=>r.id))"),['unsent-login-test'])
        self.assertIn('다시 로그인',b.evaluate("$('error').textContent"))
        self.assertEqual(self.store.objects('job'),[])

    def test_late_old_session_response_does_not_reject_a_new_login(self):
        b=self.browser_login();b.wait("!!state.moment && state.navigationPending===null")
        b.evaluate("window.realFetch=window.fetch;window.fetch=(url,options)=>url.endsWith('/session')?new Promise(resolve=>{window.expireOldSession=()=>resolve(new Response(JSON.stringify({message:'old session expired'}),{status:401}));}):realFetch(url,options);window.oldSessionRequest=api('/session').catch(()=>true);true")
        b.evaluate("api('/login','POST',{actor_id:'reviewer',secret:'studio-test-password'}).then(r=>{state.csrf=r.csrf_token;window.newCsrf=r.csrf_token;expireOldSession();return oldSessionRequest;}).then(()=>true)")
        self.assertTrue(b.evaluate("!$('workspace').hidden && $('login').hidden && state.csrf===window.newCsrf"))
