"""Live visual inference + Gemini + Atlas, using synthetic/upstream test data only."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import App, load_env


def main():
    load_env()
    report = {}
    probe_id = None
    with tempfile.TemporaryDirectory(prefix='unmute-live-mvp-') as directory:
        app = App(Path(directory) / 'test.db')
        try:
            clip = ROOT / 'artifacts' / 'upstream-visual-sample.mp4'
            result = app.transcribe({'video':base64.b64encode(clip.read_bytes()).decode(),
                                     'mime':'video/mp4','use_gemini':True})
            assert result['gemini_used'], 'Live Gemini did not return usable suggestions'
            assert result['raw'] in result['candidates']
            report['model_and_gemini'] = {key:result[key] for key in ['source','model','raw','candidates','visual_candidates','timing']}
            assert not app.store.state()['requests'], 'Inference alone must never send a request'
            if app.atlas.client:
                decision = app.store.decision(['Synthetic Unmute MVP connectivity test'], '', 'demo', True)
                request = app.post('/api/confirm',{**decision,'choice':0,'confirmed':True})
                probe_id = request['id']
                app.atlas.events.join()
                collection = app.atlas.client[os.environ.get('MONGODB_DATABASE','unmute')].requests
                assert collection.find_one({'_id':probe_id})['status']=='pending'
                app.post('/api/request-status',{'id':probe_id,'status':'acknowledged'})
                app.atlas.events.join()
                assert collection.find_one({'_id':probe_id})['status']=='acknowledged'
                assert app.store.state()['pending_sync']==0
                report['atlas'] = {'write':True,'acknowledgment':True,'outbox_drained':True}
        finally:
            if probe_id and app.atlas.client:
                report['test_document_removed'] = app.atlas.client[os.environ.get('MONGODB_DATABASE','unmute')].requests.delete_one({'_id':probe_id}).deleted_count==1
            app.model.close();app.atlas.close();app.store.db.close()
    (ROOT/'artifacts'/'live-mvp-check.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
