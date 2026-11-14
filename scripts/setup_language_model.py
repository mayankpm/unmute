"""Prepare the upstream English decoding LM as an optional local accuracy experiment.
Does not change .env. Benchmark the new .ini before choosing it for the app.
"""
from configparser import ConfigParser
from pathlib import Path
import ssl
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    tls = ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').exists() else ssl.create_default_context()
    archive = ROOT/'models'/'english-decoder-lm.zip'
    if not archive.exists():
        with urllib.request.urlopen('https://bit.ly/3FE4XsV',context=tls,timeout=30) as response:
            resolved = response.geturl()
        code = 'import gdown,re,sys; i=re.search(r"/d/([^/]+)",sys.argv[1]).group(1); gdown.download(id=i,output=sys.argv[2],quiet=True,use_cookies=False,verify="/etc/ssl/cert.pem",timeout=60)'
        subprocess.run([str(ROOT/'.model-venv'/'bin'/'python'),'-c',code,resolved,str(archive)],check=True)
    destination = ROOT/'models'/'english-decoder'
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if not (destination/entry.filename).resolve().is_relative_to(destination.resolve()):
                raise RuntimeError('Unsafe archive path')
        bundle.extractall(destination)
    weights = list(destination.rglob('model.pth'))
    if len(weights) != 1: raise RuntimeError('Unexpected language model archive')
    config = ConfigParser()
    config.read(ROOT/'models'/'unmute-visual.ini')
    config['model']['rnnlm'] = str(weights[0])
    config['model']['rnnlm_conf'] = str(weights[0].with_suffix('.json'))
    config['decode']['lm_weight'] = '.3'
    path = ROOT/'models'/'unmute-visual-lm.ini'
    with path.open('w') as output: config.write(output)
    print('Optional upstream English decoder prepared:',path)


if __name__=='__main__':main()
