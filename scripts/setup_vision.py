"""Download browser-local face tracking assets. No camera data leaves the browser."""
from pathlib import Path
import hashlib
import json
import shutil
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'web' / 'assets' / 'vision'
VERSION = '0.10.21'


def main():
    context = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').exists() else ssl.create_default_context()
    base = f'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@{VERSION}'
    files = {
        'vision_bundle.mjs': base + '/vision_bundle.mjs',
        'wasm/vision_wasm_internal.js': base + '/wasm/vision_wasm_internal.js',
        'wasm/vision_wasm_internal.wasm': base + '/wasm/vision_wasm_internal.wasm',
        'wasm/vision_wasm_nosimd_internal.js': base + '/wasm/vision_wasm_nosimd_internal.js',
        'wasm/vision_wasm_nosimd_internal.wasm': base + '/wasm/vision_wasm_nosimd_internal.wasm',
        'face_landmarker.task': 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
    }
    manifest = {'package': '@mediapipe/tasks-vision', 'version': VERSION, 'files': []}
    for relative, url in files.items():
        path = DEST / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with urllib.request.urlopen(url, context=context, timeout=90) as response, path.with_suffix(path.suffix + '.partial').open('wb') as output:
                shutil.copyfileobj(response, output)
            path.with_suffix(path.suffix + '.partial').replace(path)
        manifest['files'].append({'file': relative, 'source': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'Local face tracking ready: {len(files)} assets, MediaPipe {VERSION}')


if __name__ == '__main__':
    main()
