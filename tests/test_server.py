import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import App, InputError, Store, local_suggestions, gemini_suggestions


class CommunicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY":"", "MONGODB_URI":""})
        self.env.start()
        self.app = App(Path(self.tmp.name) / 'test.db')
        self.store = self.app.store

    def tearDown(self):
        self.store.db.close()
        self.env.stop()
        self.tmp.cleanup()

    def choose(self, source='quick', **kwargs):
        return self.app.post('/api/choices', {'source': source, 'phrase_id': 'water', **kwargs})

    def confirm(self, decision, **kwargs):
        return self.app.post('/api/confirm', {**decision, 'choice':0, 'confirmed':True, **kwargs})

    def test_candidates_do_not_send_a_request(self):
        self.choose()
        self.assertEqual(self.store.state()['requests'], [])

    def test_explicit_confirmation_required(self):
        decision = self.choose()
        for value in (False, 'true', 1, None):
            with self.assertRaises(InputError):
                self.confirm(decision, confirmed=value)

    def test_confirm_is_idempotent(self):
        decision = self.choose()
        self.assertEqual(self.confirm(decision)['id'], self.confirm(decision)['id'])
        self.assertEqual(len(self.store.state()['requests']), 1)

    def test_choice_validation(self):
        decision = self.choose()
        for choice in (-1, 5, True, '0'):
            with self.assertRaises(InputError):
                self.confirm(decision, choice=choice)

    def test_expired_decision_is_rejected(self):
        decision = self.choose()
        self.store.db.execute('UPDATE decisions SET created=0')
        with self.assertRaises(InputError):
            self.confirm(decision)

    def test_demo_excluded_from_metrics_and_memory(self):
        decision = self.choose('demo', candidates=['I need water'])
        request = self.confirm(decision)
        self.assertEqual(request['simulated'], 1)
        self.assertEqual(self.store.state()['metrics']['confirmed'], 0)
        self.assertEqual(self.store.memory(), [])

    def test_acknowledgment_is_explicit_and_monotonic(self):
        request = self.confirm(self.choose())
        self.assertIsNone(request['acknowledged_at'])
        ack = self.store.update_request(request['id'], 'acknowledged')
        self.assertIsNotNone(ack['acknowledged_at'])
        done = self.store.update_request(request['id'], 'resolved')
        self.assertEqual(done['acknowledged_at'], ack['acknowledged_at'])
        self.assertEqual(self.store.update_request(request['id'], 'acknowledged')['status'], 'resolved')

    def test_urgent_phrase_not_invented_from_negation(self):
        decision = self.choose('local-visual', candidates=['I am not in pain'])
        self.assertEqual(self.confirm(decision)['urgent'], 0)
        request = self.confirm(self.choose(phrase_id='pain'))
        self.assertEqual(request['urgent'], 1)

    def test_model_capitalization_retains_predefined_help_signal(self):
        request = self.confirm(self.choose('local-visual', candidates=['I AM IN PAIN.']))
        self.assertEqual(request['urgent'], 1)

    def test_memory_only_after_confirmation(self):
        decision = self.app.post('/api/interpret', {'raw':'call my dotter'})
        self.assertEqual(self.store.memory(), [])
        self.confirm(decision, choice=1)
        self.assertEqual(self.store.memory()[0]['confirmed'], 'call my daughter')
        self.assertEqual(self.store.state()['metrics']['corrected'], 1)

    def test_local_suggestions_preserve_negation(self):
        result = local_suggestions('I do not need wader', [])
        self.assertEqual(result, ['I do not need wader', 'I do not need water'])

    def test_help_bypasses_model(self):
        request = self.app.post('/api/help', {'confirmed':True})
        self.assertEqual(request['text'], 'Please help me')
        self.assertEqual(request['urgent'], 1)

    def test_profile_persists(self):
        self.store.save_profile({'name':'Priya', 'room':'Bed 02', 'scan_ms':100})
        other = Store(self.store.path)
        self.assertEqual(other.profile()['name'], 'Priya')
        self.assertEqual(other.profile()['scan_ms'], 800)
        other.db.close()

    def test_gemini_failure_retains_raw(self):
        with patch('server.gemini_suggestions', side_effect=TimeoutError()):
            result = self.app.post('/api/interpret', {'raw':'do not call my family','use_gemini':True})
        self.assertEqual(result['candidates'][0], 'do not call my family')
        self.assertTrue(result['warning'])

    def test_visual_unknown_does_not_silently_use_demo(self):
        with self.assertRaises(InputError):
            self.app.post('/api/transcribe', {'video':'eA=='})

    def test_request_text_cannot_be_substituted_at_confirmation(self):
        decision = self.choose()
        request = self.confirm(decision, text='Something unconfirmed')
        self.assertEqual(request['text'], 'I need water')

    def test_unconfigured_gemini_does_not_claim_live_use(self):
        result = self.app.check_integration('gemini')
        self.assertEqual(result['status'], 'not_configured')
        self.assertEqual(self.store.state()['requests'], [])

    def test_gemini_check_uses_synthetic_data_only(self):
        self.store.save_profile({'name':'Alex','room':'Bed 1','context':'private patient context'})
        response = {'candidates':['Call my daughter','Call my doctor','call my dotter'],
                    'question':'Daughter or doctor?', 'model':'fixture-model'}
        with patch('server.gemini_suggestions', return_value=response) as provider:
            result = self.app.check_integration('gemini')
        provider.assert_called_once_with('call my dotter', {'context':'','names':''}, [])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['model'], 'fixture-model')
        self.assertEqual(self.store.state()['requests'], [])

    def test_gemini_errors_do_not_leak_secrets(self):
        error = urllib.error.HTTPError('https://provider.example?key=secret',429,'secret',{},None)
        with patch('server.gemini_suggestions', side_effect=error):
            result = self.app.check_integration('gemini')
        self.assertEqual(result['status'],'failed')
        self.assertIn('quota',result['message'])
        self.assertNotIn('secret',json.dumps(result))

    def test_atlas_check_reads_without_creating_requests(self):
        client = MagicMock()
        client.__getitem__.return_value.requests.count_documents.return_value=7
        self.app.atlas.client=client
        result=self.app.check_integration('atlas')
        client.admin.command.assert_called_once_with('ping')
        client.__getitem__.return_value.requests.count_documents.assert_called_once_with({},maxTimeMS=2500)
        client.__getitem__.return_value.requests.replace_one.assert_not_called()
        self.assertEqual(result['document_count'],7)
        self.assertEqual(result['status'],'verified')

    def test_gemini_rewrites_retain_raw_transcript(self):
        output={'candidates':['I need water','Call my daughter','Please help me'],'question':'Which request?'}
        response={'modelVersion':'fixture-model','candidates':[{'content':{'parts':[{'text':json.dumps(output)}]}}]}
        fake=MagicMock()
        fake.__enter__.return_value=io.BytesIO(json.dumps(response).encode())
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test-key'}), patch('server.urllib.request.urlopen',return_value=fake):
            result=gemini_suggestions('not water',{'context':'','names':''},[])
        self.assertEqual(result['candidates'],['I need water','Call my daughter','not water'])
        self.assertEqual(result['model'],'fixture-model')

    def test_empty_gemini_response_is_rejected(self):
        output={'candidates':[],'question':'Which request?'}
        fake=MagicMock()
        fake.__enter__.return_value=io.BytesIO(json.dumps({'candidates':[{'content':{'parts':[{'text':json.dumps(output)}]}}]}).encode())
        with patch.dict(os.environ,{'GEMINI_API_KEY':'test-key'}), patch('server.urllib.request.urlopen',return_value=fake):
            with self.assertRaises(InputError):
                gemini_suggestions('not water',{'context':'','names':''},[])


if __name__ == '__main__':
    unittest.main()
