"""Job history must not be decoded to navigate or poll an empty queue."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from apps.guardsynth_studio.jobs import Worker
from apps.guardsynth_studio.sequence import latest_stage
from apps.guardsynth_studio.store import Store
from .helpers import fixture


class JobQueriesTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store, self.service, self.ids, self.extraction, _, _ = fixture(self.temp.name, 2)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def job(self, kind='SEQ_VERIFY', status='SUCCEEDED', extraction=None):
        return self.store.put('job', {'kind': kind, 'status': status, 'attempt': 0, 'generation': 0,
                                     'inputs': {'snapshot': {'extraction_id': extraction or self.extraction}},
                                     'result': {'large_history': 'x' * 20000}})

    def test_queries_preserve_order_and_filter_stage_extraction_and_status(self):
        first = self.job()
        self.job(extraction='other-extraction')
        self.job(kind='SEQ_EBLC')
        latest = self.job(status='QUEUED')
        self.assertEqual(self.store.job_ids(kind='SEQ_VERIFY', extraction=self.extraction), [first, latest])
        self.assertEqual(self.store.job_ids(kind='SEQ_VERIFY', extraction=self.extraction,
                                            newest_first=True, limit=1), [latest])
        self.assertEqual(self.store.job_ids(kind='SEQ_VERIFY', extraction=self.extraction,
                                            statuses=('SUCCEEDED',)), [first])
        self.assertEqual(self.store.job_ids(statuses=()), [])
        self.assertEqual(latest_stage(self.service, self.extraction, 'SEQ_VERIFY')['id'], latest)
        self.assertEqual(self.store.job(first)['id'], first)

    def test_status_updates_are_immediately_visible_without_cached_history(self):
        identity = self.job(status='QUEUED')
        worker = Worker(self.service)
        claimed = worker.claim()
        self.assertEqual(claimed['id'], identity)
        self.assertEqual(claimed['status'], 'RUNNING')
        self.assertEqual(self.store.job_ids(statuses=('QUEUED',)), [])
        self.assertEqual(self.store.job_ids(statuses=('RUNNING',)), [identity])
        claimed.update(status='CANCELLED')
        self.store.put('job', claimed, identity)
        self.assertEqual(self.store.job_ids(statuses=('RUNNING',)), [])
        self.assertEqual(latest_stage(self.service, self.extraction, 'SEQ_VERIFY')['status'], 'CANCELLED')
        claimed.update(status='QUEUED')
        self.store.put('job', claimed, identity)
        self.assertEqual(worker.claim()['attempt'], 2)

    def test_idle_worker_does_not_load_completed_history(self):
        for _ in range(80): self.job()
        with (patch.object(self.store, 'objects', side_effect=AssertionError('History decoded')),
              patch.object(self.store, 'get', side_effect=AssertionError('Completed job loaded'))):
            self.assertFalse(Worker(self.service).run_once())

    def test_recovery_changes_only_running_jobs(self):
        done = self.job()
        queued = self.job(status='QUEUED')
        vlm = self.job(kind='SEQ_COC', status='RUNNING')
        check = self.job(status='RUNNING')
        before = {i: deepcopy(self.store.job(i)) for i in (done, queued)}
        with patch.object(self.store, 'objects', side_effect=AssertionError('History decoded')):
            Worker(self.service).recover()
        self.assertEqual(self.store.job(vlm)['status'], 'OUTCOME_UNKNOWN')
        self.assertEqual(self.store.job(check)['status'], 'INTERRUPTED')
        self.assertEqual(self.store.job(vlm)['generation'], 1)
        for identity, value in before.items(): self.assertEqual(self.store.job(identity), value)

    def test_existing_database_gains_indexes_without_rewriting_jobs(self):
        identity = self.job()
        before = self.store.job(identity)
        for name in ('studio_job_status', 'studio_job_stage'):
            self.store.db.execute('DROP INDEX '+name)
        self.store.close()
        self.store = Store(Path(self.temp.name))
        self.service.store = self.store
        self.assertEqual(self.store.job(identity), before)
        plan = self.store.db.execute("EXPLAIN QUERY PLAN SELECT id FROM objects WHERE kind='job' "
                                     "AND json_extract(data,'$.status')='QUEUED' ORDER BY rowid LIMIT 1").fetchall()
        self.assertIn('studio_job_status', str([tuple(r) for r in plan]))
