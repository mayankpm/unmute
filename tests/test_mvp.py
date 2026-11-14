import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import App, Store, InputError, word_errors
from model_worker import PersistentModel, ModelUnavailable


class MvpStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'MONGODB_URI': '', 'GEMINI_API_KEY': ''})
        self.env.start()
        self.app = App(Path(self.temp.name) / 'test.db')
        self.store = self.app.store

    def tearDown(self):
        self.app.model.close(); self.store.db.close(); self.env.stop(); self.temp.cleanup()

    def test_favorite_is_a_server_known_quick_phrase(self):
        phrases = self.store.favorite({'text': 'Call Priya'})['favorites']
        result = self.app.post('/api/choices', {'source':'quick', 'phrase_id':phrases[0]['id']})
        self.assertEqual(result['candidates'], ['Call Priya'])
        self.assertEqual(self.store.state()['requests'], [])

    def test_favorite_duplicates_and_removal(self):
        self.store.favorite({'text':'Call Priya'})
        self.store.favorite({'text':'Call Priya'})
        self.assertEqual(len(self.store.favorites()), 1)
        self.store.favorite({'action':'remove','id':self.store.favorites()[0]['id']})
        self.assertEqual(self.store.favorites(), [])

    def test_revision_requires_fresh_confirmation(self):
        original = self.store.decision(['Call my doctor'], 'call my dotter', 'gemini')
        edited = self.store.revise({'decision_id':original['decision_id'], 'text':'Call my daughter'})
        self.assertEqual(self.store.state()['requests'], [])
        self.assertEqual(edited['source'], 'edited')
        request = self.store.confirm({**edited, 'choice':0, 'confirmed':True})
        self.assertEqual(request['text'], 'Call my daughter')
        self.assertEqual(self.store.memory()[0]['raw'], 'call my dotter')

    def test_confirmed_decision_cannot_be_revised(self):
        original = self.store.decision(['Hello'], 'hello', 'auto-avsr')
        self.store.confirm({**original,'choice':0,'confirmed':True})
        with self.assertRaises(InputError): self.store.revise({'decision_id':original['decision_id'],'text':'Changed'})

    def test_evaluation_uses_raw_and_top_suggestion(self):
        decision = self.store.decision(['Call my daughter','call my dotter'], 'call my dotter', 'gemini')
        self.store.record_attempt(decision['decision_id'],'gemini','call my dotter',1000,700,300)
        result = self.store.evaluate({**decision, 'reference':'Call my daughter'})
        self.assertEqual(result['raw']['errors'], 1)
        self.assertEqual(result['suggestion']['errors'], 0)
        self.assertEqual(self.store.state()['evaluation']['words'], 3)
        self.assertEqual(self.store.state()['requests'], [])

    def test_evaluation_replacement_is_not_double_counted(self):
        decision = self.store.decision(['Hello'], 'hello', 'auto-avsr')
        for _ in range(2): self.store.evaluate({**decision,'reference':'Hello'})
        self.assertEqual(self.store.state()['evaluation']['clips'], 1)

    def test_typed_gemini_test_is_not_a_lipreading_evaluation(self):
        decision = self.store.decision(['Hello'], 'hello', 'gemini')
        with self.assertRaises(InputError): self.store.evaluate({**decision,'reference':'Hello'})

    def test_evaluation_rejects_simulated_and_edited_text(self):
        for source, simulated in [('demo',True),('edited',False)]:
            decision = self.store.decision(['Hello'], 'hello', source, simulated)
            with self.assertRaises(InputError): self.store.evaluate({**decision,'reference':'Hello'})

    def test_word_errors_can_exceed_100_percent(self):
        self.assertEqual(word_errors('yes','yes please call my family')['wer'], 4)
        self.assertEqual(word_errors('Call Priya!','call priya')['errors'], 0)

    def test_outbox_does_not_drop_a_newer_acknowledgment(self):
        self.store.enqueue_mirror({'id':'request','status':'pending'})
        original = self.store.pending_mirror()[0]
        self.store.enqueue_mirror({'id':'request','status':'acknowledged'})
        self.store.finish_mirror('request',original['version'])
        pending = self.store.pending_mirror()
        self.assertEqual(len(pending), 1)
        self.assertEqual(json.loads(pending[0]['payload'])['status'], 'acknowledged')
        self.store.finish_mirror('request', pending[0]['version'])
        self.assertEqual(self.store.pending_mirror(), [])

    def test_outbox_survives_restart(self):
        self.store.enqueue_mirror({'id':'request','status':'pending'})
        other = Store(self.store.path)
        self.assertEqual(other.pending_mirror()[0]['id'], 'request')
        other.db.close()


WORKER = '''import sys,json,time
print('UNMUTE_JSON:'+json.dumps({'type':'ready','startup_ms':1}),flush=True)
for line in sys.stdin:
    job=json.loads(line)
    if job['path']=='slow':time.sleep(10)
    print('UNMUTE_JSON:'+json.dumps({'id':job['id'],'text':'Hello','candidates':['Hello'],'inference_ms':1}),flush=True)
'''


class WorkerTests(unittest.TestCase):
    def setUp(self): self.worker = PersistentModel(command=[sys.executable,'-u','-c',WORKER])
    def tearDown(self): self.worker.close()

    def test_worker_is_reused(self):
        self.worker.infer('clip', timeout=3)
        pid = self.worker.process.pid
        self.worker.infer('clip', timeout=3)
        self.assertEqual(self.worker.process.pid, pid)
        self.assertEqual(self.worker.snapshot()['completed'], 2)

    def test_timeout_releases_worker_for_retry(self):
        with self.assertRaises(ModelUnavailable): self.worker.infer('slow', timeout=.4)
        self.assertEqual(self.worker.infer('clip', timeout=3)['text'], 'Hello')

    def test_cancel_releases_inflight_request(self):
        errors = []
        def work():
            try: self.worker.infer('slow',job_id='cancel-me',timeout=5)
            except ModelUnavailable as error: errors.append(str(error))
        thread = threading.Thread(target=work)
        thread.start()
        deadline = time.monotonic()+3
        while self.worker.snapshot()['status'] != 'processing' and time.monotonic()<deadline: time.sleep(.02)
        self.assertTrue(self.worker.cancel('cancel-me'))
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors)
        self.assertEqual(self.worker.infer('clip', timeout=3)['text'], 'Hello')


if __name__ == '__main__': unittest.main()
