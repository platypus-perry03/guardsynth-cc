"""Login reads the saved workspace; old drafts need explicit review."""
from copy import deepcopy
import json
import unittest

from . import test_grounded_browser as grounded
from . import test_http_browser as http
from .helpers import edit


class WorkspaceRestoreTest(unittest.TestCase):
    setUp=http.HTTPTest.setUp
    tearDown=http.HTTPTest.tearDown
    browser_login=http.HTTPTest.browser_login
    coc_candidate=grounded.GroundedBrowserTest.coc_candidate
    install_coc=grounded.GroundedBrowserTest.install_coc

    def seed_and_relogin(self, count=1):
        self.install_coc();edit(self.service,self.ids[0],'sequence_coc',{'explanation':'현재 저장된 CoC'})
        b=self.browser_login();b.wait("!!state.moment && state.navigationPending===null")
        before=deepcopy(self.store.moment(self.ids[0]))
        for i in range(count):
            row={'id':'previous-draft-'+str(i),'moment_id':self.ids[0],'revision':0,'kind':'sequence_coc',
                 'payload':{'explanation':'이전 EBLC처럼 보이는 임시 수정 '+str(i)},'created':i,'sent':False}
            b.evaluate("dbOp('put',"+json.dumps(row)+").then(()=>true)")
        b.evaluate("showStage(3);$('seq_eblc_raw').open=true;$('zoom').showModal();api('/login','POST',{actor_id:'reviewer',secret:'studio-test-password'}).then(r=>{state.csrf=r.csrf_token;return activate();}).then(()=>true)")
        b.wait("!!state.moment && state.navigationPending===null && $('seq_explanation').value==='현재 저장된 CoC'")
        return b,before

    def test_login_preserves_pending_drafts_without_modal_or_writes(self):
        b,before=self.seed_and_relogin()
        self.assertEqual(self.store.moment(self.ids[0]),before)
        self.assertTrue(b.evaluate("state.stage===1 && document.querySelectorAll('dialog[open]').length===0 && !$('drafts_notice').hidden && !$('seq_eblc_raw').open"))
        self.assertEqual(b.evaluate("dbOp('getAll').then(rows=>rows.map(r=>[r.id,r.revision,r.deferred]))"),[['previous-draft-0',0,True]])
        self.assertEqual(b.evaluate("$('error').textContent"),'')
        self.assertEqual(self.store.objects('job'),[])

    def test_new_edit_saves_without_replaying_or_rebasing_old_draft(self):
        b,before=self.seed_and_relogin()
        b.evaluate("$('seq_explanation').value='지금 검토한 수정';$('seq_explanation').dispatchEvent(new Event('input'));flush().then(()=>true)")
        self.assertEqual(self.store.moment(self.ids[0])['components']['sequence_coc']['payload']['explanation'],'지금 검토한 수정')
        self.assertEqual(b.evaluate("dbOp('getAll').then(rows=>rows.map(r=>[r.id,r.revision,r.deferred]))"),[['previous-draft-0',0,True]])
        self.assertFalse(b.evaluate("$('conflict').open"))

    def test_discard_only_removes_held_local_drafts(self):
        b,before=self.seed_and_relogin()
        b.evaluate("$('drafts_discard').click();true");b.wait("$('drafts_notice').hidden")
        self.assertEqual(b.evaluate("dbOp('getAll').then(rows=>rows.length)"),0)
        self.assertEqual(self.store.moment(self.ids[0]),before)

    def test_compare_is_explicit_and_applies_only_the_selected_draft(self):
        b,before=self.seed_and_relogin(2)
        b.evaluate("$('drafts_review').click();true");b.wait("$('conflict').open")
        self.assertEqual(self.store.moment(self.ids[0]),before)
        self.assertIn('이전 임시 수정',b.evaluate("$('conflict_diff').textContent"))
        compared=b.evaluate("JSON.parse($('conflict_diff').textContent)")
        self.assertEqual(compared['항목'],'CoC')
        self.assertEqual(compared['현재 저장본'],{'explanation':'현재 저장된 CoC'})
        b.evaluate("$('conflict_apply').click();true")
        b.wait("!$('conflict').open && $('seq_explanation').value==='이전 EBLC처럼 보이는 임시 수정 0'")
        self.assertEqual(self.store.moment(self.ids[0])['revision'],before['revision']+1)
        self.assertEqual(b.evaluate("dbOp('getAll').then(rows=>rows.map(r=>[r.id,r.revision,r.deferred]))"),[['previous-draft-1',0,True]])

    def test_reload_again_does_not_replay_deferred_drafts(self):
        b,before=self.seed_and_relogin()
        b.call('Page.reload');b.wait("document.readyState==='complete' && !!state.moment && !$('drafts_notice').hidden")
        self.assertEqual(self.store.moment(self.ids[0]),before)
        self.assertFalse(b.evaluate("$('conflict').open"))
