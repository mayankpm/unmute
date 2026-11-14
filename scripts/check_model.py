"""Smoke-test downloaded visual-only weights on upstream's sample GIF, without audio.
This checks execution, not accuracy on a new speaker or clinical suitability.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import base64
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server import load_env


def main():
    load_env()
    artifacts=ROOT/'artifacts'
    artifacts.mkdir(exist_ok=True)
    env_python=os.environ['AVSR_PYTHON']
    ffmpeg=subprocess.check_output([env_python,'-c','import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'],text=True).strip()
    clip=artifacts/'upstream-visual-sample.mp4'
    subprocess.run([ffmpeg,'-y','-i',str(Path(os.environ['AVSR_REPO'])/'doc'/'vsr_1.gif'),
                    '-t','3','-an','-vf','fps=25','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],
                   check=True,capture_output=True)
    started=time.monotonic()
    if '--api' in sys.argv:
        url=sys.argv[sys.argv.index('--api')+1].rstrip('/')
        payload=json.dumps({'video':base64.b64encode(clip.read_bytes()).decode(),'mime':'video/mp4'}).encode()
        headers={'Content-Type':'application/json'}
        if os.environ.get('UNMUTE_TOKEN'):
            headers['Authorization']='Bearer '+os.environ['UNMUTE_TOKEN']
        with urllib.request.urlopen(urllib.request.Request(url+'/api/transcribe',data=payload,headers=headers),timeout=180) as response:
            decision=json.load(response)
        assert decision['source']=='auto-avsr' and decision['candidates']==[decision['raw']]
        result={'text':decision['raw']}
    else:
        process=subprocess.run([env_python,str(ROOT/'adapters'/'auto_avsr.py'),str(clip)],
                               text=True,capture_output=True,timeout=180)
        if process.returncode:
            print(process.stderr[-12000:])
            raise SystemExit(process.returncode)
        result=json.loads(process.stdout)
    assert isinstance(result['text'],str) and result['text'].strip(),result
    report={'source':'upstream repository doc/vsr_1.gif, first 3 seconds, audio removed',
            'seconds':round(time.monotonic()-started,2),'transcript':result['text'],
            'configuration':'CPU, beam=10, no external language model',
            'accuracy':'not measured; execution smoke test only',
            'http_api_tested':'--api' in sys.argv}
    (artifacts/'model-smoke.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
