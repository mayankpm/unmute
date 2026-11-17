"""Hands-free session flow with the real model and a prerecorded face as a fake webcam:
capture -> review -> confirm -> capture resumes by itself -> tab hidden pauses -> tab visible resumes.
Uses an isolated temporary database; never connects to Atlas.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import App, Handler, ThreadingHTTPServer, load_env
from playwright.sync_api import sync_playwright, expect

SET_HIDDEN = """hidden => { Object.defineProperty(document, 'hidden', {configurable: true, get: () => hidden});
  document.dispatchEvent(new Event('visibilitychange')); }"""


def main():
    load_env()
    os.environ['MONGODB_URI'] = ''
    os.environ['UNMUTE_TOKEN'] = ''
    ffmpeg = subprocess.check_output([os.environ['AVSR_PYTHON'], '-c',
                                      'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'], text=True).strip()
    fake_camera = ROOT / 'artifacts' / 'upstream-webcam.y4m'
    if not fake_camera.exists():
        subprocess.run([ffmpeg, '-y', '-i', str(ROOT / 'artifacts' / 'upstream-visual-sample.mp4'),
                        '-an', '-vf', 'fps=25', '-pix_fmt', 'yuv420p', str(fake_camera)], check=True, capture_output=True)
    with tempfile.TemporaryDirectory(prefix='unmute-session-flow-') as directory:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        server.app = App(Path(directory) / 'test.db')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        server.app.model.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='msedge', headless=True, args=[
                    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
                    '--use-file-for-fake-video-capture=' + str(fake_camera)])
                page = browser.new_page(permissions=['camera'])
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('#connection')).to_contain_text('connected')
                status = page.locator('#session-status')
                page.locator('#session-toggle').click()
                expect(page.locator('.candidate').first).to_be_visible(timeout=120000)
                expect(status).to_have_text('Your words, your decision')
                print('1. phrase captured, choices shown:', page.locator('.candidate').all_inner_texts())
                page.locator('.candidate').first.click()
                page.locator('#confirm-button').click()
                expect(page.locator('#sent-panel')).to_be_visible()
                print('2. confirmed and sent:', page.locator('#sent-text').inner_text())
                expect(status).not_to_have_text('Your words, your decision', timeout=6000)
                print('3. capture resumed by itself after confirm ->', status.inner_text())
                page.evaluate(SET_HIDDEN, True)
                expect(status).to_have_text('Capture paused')
                print('4. tab hidden -> ', status.inner_text())
                page.evaluate(SET_HIDDEN, False)
                expect(status).not_to_have_text('Capture paused', timeout=3000)
                print('5. tab visible again -> resumed ->', status.inner_text())
                page.locator('#session-toggle').click()
                expect(status).to_have_text('Session off')
                expect(page.locator('#camera-badge')).to_have_text('Camera off')
                print('6. End session -> session off, camera off')
                browser.close()
            print('PASS: hands-free session flow')
        finally:
            server.shutdown(); server.server_close(); server.app.model.close(); server.app.atlas.close(); server.app.store.db.close()


if __name__ == '__main__':
    main()
