"""Full real-model automatic-session smoke test using an upstream prerecorded face.
Chrome presents that public silent sample as a fake webcam. No human camera is used.
The actual local landmark model, speech worker, and optional Gemini are exercised.
No request is confirmed or sent to a caregiver/Atlas.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import App, Handler, ThreadingHTTPServer, load_env
from playwright.sync_api import sync_playwright, expect


def main():
    load_env()
    # Never connect this test server to Atlas or use a LAN access token.
    os.environ['MONGODB_URI'] = ''
    os.environ['UNMUTE_TOKEN'] = ''
    ffmpeg = subprocess.check_output([os.environ['AVSR_PYTHON'],'-c',
                                     'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'],text=True).strip()
    fake_camera = ROOT/'artifacts'/'upstream-webcam.y4m'
    subprocess.run([ffmpeg,'-y','-i',str(ROOT/'artifacts'/'upstream-visual-sample.mp4'),
                    '-an','-vf','fps=25','-pix_fmt','yuv420p',str(fake_camera)],check=True,capture_output=True)
    with tempfile.TemporaryDirectory(prefix='unmute-real-session-') as directory:
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.daemon_threads=True
        server.app=App(Path(directory)/'test.db')
        threading.Thread(target=server.serve_forever,daemon=True).start()
        server.app.model.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='chrome',headless=True,args=[
                    '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
                    '--use-file-for-fake-video-capture='+str(fake_camera)])
                page=browser.new_page(permissions=['camera'])
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('#connection')).to_contain_text('connected')
                if os.environ.get('GEMINI_API_KEY'):page.locator('#avsr-gemini').check()
                before=time.monotonic()
                page.locator('#session-toggle').click()
                expect(page.locator('.candidate').first).to_be_visible(timeout=90000)
                expect(page.locator('#session-status')).to_have_text('Your words, your decision')
                assert not server.app.store.state()['requests']
                report={'status':'verified','actual_local_face_tracking':True,'automatic_video_capture':True,
                        'persistent_visual_model':True,'gemini_opt_in':bool(os.environ.get('GEMINI_API_KEY')),
                        'seconds_to_review_including_startup':round(time.monotonic()-before,2),
                        'raw_transcript':page.locator('#raw-transcript').inner_text(),
                        'candidates':page.locator('.candidate').all_inner_texts(),
                        'source':page.locator('#candidate-source').inner_text(),
                        'timing':page.locator('#attempt-timing').inner_text(),
                        'requests_sent':0,'sample':'upstream prerecorded face presented as fake webcam; not a new speaker'}
                page.screenshot(path=str(ROOT/'artifacts'/'real-session-review.png'),full_page=True)
                (ROOT/'artifacts'/'session-live-check.json').write_text(json.dumps(report,indent=2))
                print(json.dumps(report,indent=2))
                page.locator('#session-toggle').click()
                expect(page.locator('#camera-badge')).to_have_text('Camera off')
                browser.close()
        finally:
            server.shutdown();server.server_close();server.app.model.close();server.app.atlas.close();server.app.store.db.close()


if __name__=='__main__':main()
