"""Download Arduino CLI + UNO toolchain into vendor/ and compile the bedside sketch.
No firmware is uploaded. No connected device is touched.
"""
from pathlib import Path
import os
import platform
import shutil
import ssl
import subprocess
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'vendor'/'arduino'
TLS=ssl.create_default_context(cafile='/etc/ssl/cert.pem') if Path('/etc/ssl/cert.pem').exists() else ssl.create_default_context()


def main():
    TOOLS.mkdir(parents=True,exist_ok=True)
    cli=TOOLS/'arduino-cli'
    if not cli.exists():
        system=platform.system()
        arch=platform.machine()
        suffix='macOS_ARM64' if system=='Darwin' and arch=='arm64' else 'macOS_64bit' if system=='Darwin' else 'Linux_64bit'
        archive=TOOLS/'cli.tar.gz'
        url=f'https://downloads.arduino.cc/arduino-cli/arduino-cli_latest_{suffix}.tar.gz'
        with urllib.request.urlopen(url,timeout=60,context=TLS) as response,archive.open('wb') as output:
            shutil.copyfileobj(response,output)
        with tarfile.open(archive) as bundle:
            member=next(m for m in bundle.getmembers() if m.name=='arduino-cli')
            with bundle.extractfile(member) as source,cli.open('wb') as output:
                shutil.copyfileobj(source,output)
        cli.chmod(0o755)
    config=TOOLS/'arduino-cli.yaml'
    config.write_text('directories:\n'+f'  data: {TOOLS / "data"}\n  downloads: {TOOLS / "downloads"}\n  user: {TOOLS / "user"}\n')
    base=[str(cli),'--config-file',str(config)]
    subprocess.run([*base,'core','update-index'],check=True)
    subprocess.run([*base,'core','install','arduino:avr'],check=True)
    subprocess.run([*base,'lib','install','LiquidCrystal'],check=True)
    subprocess.run([*base,'compile','--fqbn','arduino:avr:uno','--build-path',str(ROOT/'artifacts'/'uno-build'),str(ROOT/'firmware'/'bedside')],check=True)


if __name__=='__main__':
    main()
