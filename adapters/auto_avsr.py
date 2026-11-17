"""Run using AVSR_PYTHON in the upstream model environment, not the app environment."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    repo = Path(os.environ["AVSR_REPO"]).expanduser().resolve()
    config = Path(os.environ["AVSR_CONFIG"]).expanduser().resolve()
    video = Path(sys.argv[1]).resolve()
    # Browser clips vary in frame rate. Normalize to the model's 25 fps and remove audio.
    import imageio_ffmpeg
    with tempfile.TemporaryDirectory(prefix='unmute-normalized-') as tmp:
        normalized = Path(tmp) / 'visual.mp4'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(video), '-an',
                        '-vf', 'fps=25,scale=640:-2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        str(normalized)], capture_output=True, check=True)
        # Use upstream's documented CLI. No shell interpolation; upstream owns mouth tracking.
        result = subprocess.run([
            sys.executable, str(repo / "infer.py"), f"config_filename={config}",
            f"data_filename={normalized}", "detector=mediapipe", "gpu_idx=-1"],
            cwd=repo, capture_output=True, text=True, env={**os.environ, 'PYTHONUTF8': '1'})
        if result.returncode:
            sys.stderr.write(result.stderr)
            raise RuntimeError('Upstream inference failed; see diagnostics above.')
    matches = re.findall(r"^hyp:\s*(.+)$", result.stdout, re.MULTILINE)
    if not matches:
        raise RuntimeError("Upstream did not return a hyp: transcript")
    print(json.dumps({"text": matches[-1].strip()}))


if __name__ == "__main__":
    main()
