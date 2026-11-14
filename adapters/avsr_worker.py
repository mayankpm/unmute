"""Persistent Auto-AVSR inference. Run only inside the separate model environment."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

PROTOCOL = sys.stdout
sys.stdout = sys.stderr


def emit(message):
    PROTOCOL.write('UNMUTE_JSON:' + json.dumps(message) + '\n')
    PROTOCOL.flush()


def main():
    started = time.monotonic()
    repo = Path(os.environ['AVSR_REPO']).expanduser().resolve()
    sys.path.insert(0, str(repo))
    os.chdir(repo)
    try:
        import torch
        import imageio_ffmpeg
        from pipelines.pipeline import InferencePipeline
        from espnet.asr.asr_utils import add_results_to_json
        torch.set_num_threads(int(os.environ.get('AVSR_THREADS', '4')))
        pipeline = InferencePipeline(os.environ['AVSR_CONFIG'], detector='mediapipe', face_track=True, device='cpu')
        emit({'type': 'ready', 'startup_ms': round((time.monotonic() - started) * 1000)})
    except Exception:
        emit({'type': 'startup_error'})
        return
    for line in sys.stdin:
        job_id = None
        try:
            job = json.loads(line)
            job_id = job['id']
            before = time.monotonic()
            with tempfile.TemporaryDirectory(prefix='unmute-inference-') as directory:
                normalized = Path(directory) / 'silent.mp4'
                command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-ss', str(job.get('trim_start', 0)),
                           '-i', job['path'], '-an']
                if job.get('duration') is not None:
                    command += ['-t', str(job['duration'])]
                command += ['-vf', 'fps=25,scale=640:-2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(normalized)]
                subprocess.run(command, check=True, capture_output=True, timeout=15)
                with torch.inference_mode():
                    landmarks = pipeline.process_landmarks(str(normalized), None)
                    data = pipeline.dataloader.load_data(str(normalized), landmarks)
                    encoded = pipeline.model.model.encode(data.to('cpu'))
                    hypotheses = pipeline.model.beam_search(encoded)
                    candidates = []
                    for hypothesis in hypotheses[:3]:
                        text = add_results_to_json([hypothesis.asdict()], pipeline.model.token_list)
                        text = text.replace('▁', ' ').replace('<eos>', '').strip()
                        if text and text not in candidates:
                            candidates.append(text)
                if not candidates:
                    raise ValueError('empty transcript')
            emit({'id': job_id, 'text': candidates[0], 'candidates': candidates,
                  'inference_ms': round((time.monotonic() - before) * 1000)})
        except AssertionError:
            emit({'id': job_id, 'error': 'no_face'})
        except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            emit({'id': job_id, 'error': 'bad_video'})
        except Exception:
            emit({'id': job_id, 'error': 'inference_failed'})


if __name__ == '__main__':
    main()
