"""Regression checks for real browser recording and delayed/failing processing.
Uses synthetic webcam video, a temporary database, and a controlled model stub.
"""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import App, Handler, InputError, ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect


class RecordingApp(App):
    def __init__(self, path):
        super().__init__(path)
        self.release = threading.Event()
        self.received_video = False
        self.calls = 0
        self.fail_inference = False

    def config(self):
        return {**super().config(), 'avsr': True}

    def transcribe(self, obj):
        self.calls += 1
        self.received_video = bool(obj.get('video'))
        self.release.wait(timeout=15)
        if self.fail_inference:
            raise InputError('Test model could not read this clip. Please record again.')
        return {**self.store.decision(['I need water'], 'I need water', 'auto-avsr'),
                'raw': 'I need water'}


def main():
    for key in ['GEMINI_API_KEY', 'MONGODB_URI', 'UNMUTE_TOKEN']:
        os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='unmute-recording-test-') as directory:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        server.app = RecordingApp(Path(directory) / 'test.db')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='chrome', headless=True, args=[
                    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
                page = browser.new_page(permissions=['camera'])
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('#connection')).to_contain_text('connected')
                page.locator('#recognition-mode').select_option('avsr')
                page.locator('#phrase-match').uncheck()  # this test covers the open-sentence path
                page.locator('#camera-start').click()
                expect(page.locator('#camera-badge')).to_have_text('Camera active')
                page.locator('#record-button').click()
                expect(page.locator('#capture-message')).to_have_text('Reading your lips…', timeout=12000)
                for _ in range(20):
                    if server.app.received_video:
                        break
                    page.wait_for_timeout(50)
                assert server.app.received_video, 'Real video must reach the upload handler'
                if '--observe' in sys.argv:
                    print(json.dumps({'phase': page.locator('#capture-message').inner_text(),
                                      'counter': page.locator('#capture-clock').inner_text()}))
                else:
                    expect(page.locator('#capture-overlay')).to_have_attribute('data-phase', 'processing')
                    expect(page.locator('#capture-clock')).to_have_text(re.compile(r'^\d+s elapsed$'))
                    first = page.locator('#capture-clock').inner_text()
                    expect(page.locator('#capture-clock')).not_to_have_text(first, timeout=3000)
                    expect(page.locator('#camera-hint')).to_contain_text('Recording finished')
                    expect(page.locator('#record-button')).to_be_disabled()
                server.app.release.set()
                expect(page.locator('.candidate')).to_have_count(1)
                expect(page.locator('#capture-overlay')).to_be_hidden()
                expect(page.locator('#record-button')).to_be_enabled()
                if '--observe' not in sys.argv:
                    page.locator('#none-button').click()
                    previous_calls = server.app.calls
                    page.locator('#record-button').click()
                    expect(page.locator('#capture-message')).to_have_text('Recording your words', timeout=8000)
                    page.locator('#capture-cancel').click()
                    expect(page.locator('#capture-overlay')).to_be_hidden()
                    expect(page.locator('#record-button')).to_be_enabled()
                    expect(page.locator('#camera-hint')).to_contain_text('Attempt canceled')
                    assert server.app.calls == previous_calls, 'Canceled capture must not be uploaded'
                    server.app.fail_inference = True
                    page.locator('#record-button').click()
                    expect(page.locator('#camera-hint')).to_contain_text('could not read this clip', timeout=12000)
                    expect(page.locator('#capture-overlay')).to_be_hidden()
                    expect(page.locator('#record-button')).to_be_enabled()
                    server.app.fail_inference = False
                    # Exercise missing MediaRecorder.onstop: the UI must recover.
                    page.evaluate('''() => { window.MediaRecorder = class {
                      static isTypeSupported() { return true; }
                      constructor() { this.state = 'inactive'; }
                      start() { this.state = 'recording'; }
                      stop() { this.state = 'inactive'; }
                    }; }''')
                    page.locator('#record-button').click()
                    expect(page.locator('#camera-hint')).to_contain_text('could not finish saving', timeout=18000)
                    expect(page.locator('#capture-overlay')).to_be_hidden()
                    expect(page.locator('#record-button')).to_be_enabled()
                    assert not errors, errors
                    print('PASS: real silent video capture, recording-to-processing transition, elapsed time, delayed inference, successful recovery, and recorder-finalization watchdog')
                browser.close()
        finally:
            server.app.release.set()
            server.shutdown()
            server.server_close()
            server.app.store.db.close()


if __name__ == '__main__':
    main()
