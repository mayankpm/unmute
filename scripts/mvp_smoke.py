"""MVP browser flow: automatic capture, review, repair, evaluation, favorites.
Uses a synthetic webcam and controlled geometry/model fixtures. No live API calls.
Real browser landmark/model inference is verified by the separate smoke scripts.
"""
import os
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import App, Handler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect


class FakeModel:
    startup_ms = 1
    def snapshot(self): return {'status':'ready','loaded':True}
    def start(self): return self.snapshot()
    def cancel(self, job): return True


class MvpApp(App):
    def __init__(self, path):
        super().__init__(path); self.model = FakeModel(); self.clips = []
    def config(self): return {**super().config(), 'gemini':True, 'avsr':True, 'face_tracking':True}
    def transcribe(self, obj):
        assert obj.get('video') and 0 <= obj.get('trim_start',0) <= 30
        self.clips.append(obj)
        result = self.store.decision(['I need water','I need wader'], 'I need wader', 'gemini')
        self.store.record_attempt(result['decision_id'],'gemini','I need wader',1000,700,300)
        return {**result, 'raw':'I need wader', 'question':'Did you mean water?', 'model':'test-fixture',
                'gemini_used':True, 'timing':{'total_ms':1000,'inference_ms':700,'gemini_ms':300}}


def main():
    for key in ['MONGODB_URI','GEMINI_API_KEY','UNMUTE_TOKEN']: os.environ.pop(key,None)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.daemon_threads = True
        server.app = MvpApp(Path(directory)/'test.db')
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='chrome',headless=True,args=[
                    '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
                page = browser.new_page(permissions=['camera'],viewport={'width':1440,'height':1100})
                page.add_init_script('''
                  window.geometryMode='quiet'; window.geometryFrame=0;
                  window.Worker=class {
                    postMessage(message){
                      if(message.type==='init'){
                        setTimeout(()=>this.onmessage?.({data:{type:'ready'}}),5);return;
                      }
                      message.bitmap?.close();
                      const n=window.geometryFrame++;
                      const speaking=window.geometryMode==='speaking' && n<12;
                      const openness=speaking ? (n%2 ? .18 : .03) : .03;
                      setTimeout(()=>this.onmessage?.({data:{type:'geometry',faceFound:true,
                        openness,widthRatio:.6,center:{x:.5,y:.5},yaw:0,
                        face:{left:.3,right:.7,top:.15,bottom:.85},mouth:{x:.5,y:.65,w:.2,h:.1}}}),5);
                    }
                    terminate(){this.onmessage=null;}
                  };
                ''')
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('#connection')).to_contain_text('connected')
                page.locator('[data-view="settings"]').click()
                page.locator('#auto-speak').uncheck()
                page.locator('[data-view="patient"]').click()
                page.locator('#avsr-gemini').check()
                page.locator('#session-toggle').click()
                expect(page.locator('#session-status')).to_have_text('Ready for your words',timeout=10000)
                page.wait_for_timeout(1200)
                assert not server.app.clips,'Quiet faces must not generate model calls'
                page.evaluate('window.geometryMode="speaking";window.geometryFrame=0')
                expect(page.locator('#session-status')).to_have_text('Capturing your phrase',timeout=5000)
                expect(page.locator('.candidate')).to_have_count(2,timeout=10000)
                expect(page.locator('#session-status')).to_have_text('Your words, your decision')
                assert len(server.app.clips)==1 and server.app.clips[0]['use_gemini']
                assert server.app.store.state()['requests']==[],'Automatic capture must not speak/send'
                page.locator('#evaluation-panel summary').click()
                page.locator('#evaluation-reference').fill('I need water')
                page.get_by_role('button',name='Measure this attempt',exact=True).click()
                expect(page.locator('#evaluation-feedback')).to_contain_text('1/3')
                page.locator('.candidate').first.click()
                page.locator('#edit-toggle').click()
                expect(page.locator('#confirm-button')).to_be_disabled()
                page.locator('[data-word="2"]').click()
                page.locator('#word-replacement').fill('tea')
                page.get_by_role('button',name='Apply word',exact=True).click()
                page.get_by_role('button',name='Review corrected sentence',exact=True).click()
                expect(page.locator('#selected-text')).to_have_text('I need tea')
                assert server.app.store.state()['requests']==[]
                page.locator('#confirm-button').click()
                expect(page.locator('#sent-text')).to_have_text('I need tea')
                page.locator('#save-phrase-button').click()
                expect(page.locator('#save-phrase-button')).to_have_text('Saved to my phrases')
                expect(page.locator('.phrase-button').filter(has_text='I need tea')).to_have_count(1)
                assert server.app.store.state()['evaluation']['clips']==1
                page.wait_for_timeout(1200)
                assert len(server.app.clips)==1,'Capture remains paused during review'
                page.screenshot(path=str(root/'artifacts'/'mvp-session-desktop.png'),full_page=True)
                page.locator('#session-toggle').click()
                expect(page.locator('#camera-badge')).to_have_text('Camera off')
                expect(page.locator('#session-status')).to_have_text('Session off')
                page.locator('[data-view="insights"]').click()
                expect(page.locator('#evaluation-summary')).to_contain_text('33%')
                page.screenshot(path=str(root/'artifacts'/'mvp-insights.png'),full_page=True)
                page.locator('[data-view="patient"]').click()
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path=str(root/'artifacts'/'mvp-session-mobile.png'),full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not errors,errors
                print('PASS: silence gating, automatic phrase capture, pause-for-review, Gemini opt-in, word repair, reference-based evaluation, personal phrases, session stop, camera release, and responsive layout')
                browser.close()
        finally:
            server.shutdown();server.server_close();server.app.store.db.close()


if __name__=='__main__': main()
