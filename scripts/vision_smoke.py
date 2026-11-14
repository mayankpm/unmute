"""Verify actual offline browser landmark inference on the upstream silent sample."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import App, Handler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright


def main():
    for key in ['GEMINI_API_KEY', 'MONGODB_URI', 'UNMUTE_TOKEN']:
        os.environ.pop(key, None)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        server.app = App(Path(directory) / 'test.db')
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='chrome', headless=True)
                page = browser.new_page()
                page.route('**/vision-test.mp4', lambda route: route.fulfill(
                    body=(root / 'artifacts' / 'upstream-visual-sample.mp4').read_bytes(), content_type='video/mp4'))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                result = page.evaluate('''async () => {
                  const {FaceTracker} = await import('/tracker.js');
                  const video = document.createElement('video');
                  video.src = '/vision-test.mp4'; video.muted = true; video.loop = true;
                  document.body.appendChild(video); await video.play();
                  const tracker = new FaceTracker();
                  const result = new Promise((resolve, reject) => {
                    const timer = setTimeout(() => reject(new Error('No face detected in the sample')), 20000);
                    tracker.addEventListener('geometry', event => {
                      if (event.detail.faceFound) { clearTimeout(timer); resolve(event.detail); }
                    });
                  });
                  await tracker.start(video);
                  try { return await result; }
                  finally { tracker.stop(); video.pause(); video.remove(); }
                }''')
                assert result['faceFound'] and result['mouth']['w'] > 0 and result['openness'] >= 0
                report = {'status': 'verified', 'local_wasm_face_tracking': True,
                          'sample': 'upstream silent video', 'mouth_geometry_received': True}
                (root / 'artifacts' / 'vision-smoke.json').write_text(json.dumps(report, indent=2))
                print(json.dumps(report))
                browser.close()
        finally:
            server.shutdown(); server.server_close(); server.app.store.db.close()


if __name__ == '__main__':
    main()
