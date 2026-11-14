"""Download upstream inference code and research weights into this workspace.

Usage: .venv/bin/python scripts/setup_avsr.py
Requires uv installed in .venv. Uses an isolated Python 3.11 environment.
"""
from pathlib import Path
from configparser import ConfigParser
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor'
REPO = VENDOR / 'Visual_Speech_Recognition_for_Multiple_Languages'
TLS = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').exists() else ssl.create_default_context()


def download(url, target):
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent':'Unmute-hackathon-prototype'})
    with urllib.request.urlopen(request, timeout=60, context=TLS) as response, target.with_suffix('.partial').open('wb') as output:
        shutil.copyfileobj(response, output)
    target.with_suffix('.partial').replace(target)


def main():
    if '--activate-only' in sys.argv:
        activate()
        return
    VENDOR.mkdir(exist_ok=True)
    uv = ROOT / '.venv' / 'bin' / 'uv'
    runtime = VENDOR / 'python'
    subprocess.run([str(uv), '--cache-dir', str(VENDOR / 'uv-cache'), 'python', 'install', '3.11',
                    '--install-dir', str(runtime), '--no-bin'], check=True)
    python = sorted(runtime.glob('cpython-3.11*/bin/python3.11'))[-1]
    env_python = ROOT / '.model-venv' / 'bin' / 'python'
    if not env_python.exists():
        subprocess.run([str(python), '-m', 'venv', str(ROOT / '.model-venv')], check=True)
    if not REPO.exists():
        with urllib.request.urlopen('https://api.github.com/repos/mpc001/Visual_Speech_Recognition_for_Multiple_Languages/commits/master',timeout=30,context=TLS) as response:
            revision=json.load(response)['sha']
        archive=VENDOR/'upstream-avsr.zip'
        download(f'https://codeload.github.com/mpc001/Visual_Speech_Recognition_for_Multiple_Languages/zip/{revision}',archive)
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                if not (VENDOR / entry.filename).resolve().is_relative_to(VENDOR.resolve()):
                    raise RuntimeError('Unsafe archive path')
            bundle.extractall(VENDOR)
            extracted = VENDOR / bundle.namelist()[0].split('/')[0]
        extracted.rename(REPO)
        (VENDOR/'avsr-provenance.json').write_text(json.dumps({'repository':'https://github.com/mpc001/Visual_Speech_Recognition_for_Multiple_Languages','revision':revision},indent=2))
    # Versions compatible with upstream's older PyTorch and MediaPipe solutions APIs.
    packages = ['torch==2.2.2','torchvision==0.17.2','torchaudio==2.2.2','numpy==1.26.4',
                'mediapipe==0.10.21','opencv-python==4.11.0.86','opencv-contrib-python==4.11.0.86',
                'hydra-core>=1.3,<1.4','scipy','scikit-image','av','six','sentencepiece',
                'pyyaml','gdown','imageio-ffmpeg','typeguard<3','tqdm']
    subprocess.run([str(uv),'--cache-dir',str(VENDOR/'uv-cache'),'pip','install','--python',str(env_python),*packages],check=True)
    # Upstream model zoo's visual-only AutoAVSR weights. Google Drive may enforce quotas.
    models = ROOT/'models'
    models.mkdir(exist_ok=True)
    archive = models/'autoavsr-visual.zip'
    if not archive.exists():
        with urllib.request.urlopen('https://bit.ly/40EAtyX',timeout=30,context=TLS) as response:
            resolved=response.geturl()
        code='import gdown,re,sys; file_id=re.search(r"/d/([^/]+)",sys.argv[1]).group(1); result=gdown.download(id=file_id,output=sys.argv[2],quiet=True,use_cookies=False,verify="/etc/ssl/cert.pem",timeout=60); sys.exit(0 if result else 1)'
        print('Downloading the upstream visual-only weights (about 891 MB)…', flush=True)
        subprocess.run([str(env_python),'-c',code,resolved,str(archive)],check=True)
    print(f'Upstream code: {REPO}',flush=True)
    print(f'Model archive: {archive}',flush=True)
    activate()


def activate():
    destination = REPO/'benchmarks'/'LRS3'/'models'
    weight = destination/'LRS3_V_WER19.1'/'model.pth'
    if not weight.exists():
        with zipfile.ZipFile(ROOT/'models'/'autoavsr-visual.zip') as bundle:
            for entry in bundle.infolist():
                if not (destination/entry.filename).resolve().is_relative_to(destination.resolve()):
                    raise RuntimeError('Unsafe model archive path')
            bundle.extractall(destination)
    config = ConfigParser()
    config.read(REPO/'configs'/'LRS3_V_WER19.1.ini')
    config['model']['model_path'] = str(weight)
    config['model']['model_conf'] = str(weight.with_suffix('.json'))
    # Local prototype uses no external LM and a smaller beam for CPU responsiveness.
    # This does NOT reproduce the published benchmark configuration or WER.
    config['model']['rnnlm'] = ''
    config['model']['rnnlm_conf'] = ''
    config['decode']['lm_weight'] = '0.0'
    config['decode']['beam_size'] = '10'
    output_config = ROOT/'models'/'unmute-visual.ini'
    with output_config.open('w') as output:
        config.write(output)
    env_path = ROOT/'.env'
    env = env_path.read_text() if env_path.exists() else (ROOT/'.env.example').read_text()
    settings = {'AVSR_PYTHON':str(ROOT/'.model-venv'/'bin'/'python'), 'AVSR_REPO':str(REPO),
                'AVSR_CONFIG':str(output_config)}
    for key, value in settings.items():
        if re.search(rf'^{key}=\s*$', env, re.MULTILINE):
            env = re.sub(rf'^{key}=\s*$', lambda match:f'{key}={value}', env, flags=re.MULTILINE)
        elif not re.search(rf'^{key}=',env,re.MULTILINE):
            env += f'\n{key}={value}\n'
    env_path.write_text(env)
    print('Visual model configured in .env. Restart the server to enable Open sentences.',flush=True)


if __name__=='__main__':
    main()
