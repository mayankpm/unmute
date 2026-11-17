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


def tokenize(phrase, vocab):
    """Split a phrase into the model's unigram pieces (fewest pieces per word). None if impossible."""
    ids = []
    for word in ''.join(c if c.isalnum() or c in " '" else ' ' for c in phrase.upper()).split():
        n = len(word)
        best = [None] * (n + 1)  # best[i] = shortest piece list covering word[:i]
        best[0] = []
        for end in range(1, n + 1):
            for start in range(end):
                if best[start] is None:
                    continue
                piece = ('▁' if start == 0 else '') + word[start:end]
                if piece in vocab and (best[end] is None or len(best[start]) + 1 < len(best[end])):
                    best[end] = best[start] + [vocab[piece]]
        if best[n] is None:
            return None
        ids += best[n]
    return ids or None


def score_phrases(model, encoded, phrases, vocab, ctc_weight=0.1):
    """Log-probability of each phrase given the video: the same CTC + attention mix the decoder uses."""
    import torch
    from espnet.nets.pytorch_backend.transformer.mask import subsequent_mask
    usable = [(p, tokenize(p, vocab)) for p in phrases]
    usable = [(p, t) for p, t in usable if t]
    if not usable:
        return []
    device = encoded.device
    eos = model.eos
    n, longest = len(usable), max(len(t) for _, t in usable)
    # Attention decoder: teacher-forced log P(tokens + <eos> | video)
    ys_in = torch.full((n, longest + 1), eos, dtype=torch.long, device=device)
    for i, (_, t) in enumerate(usable):
        ys_in[i, 1:len(t) + 1] = torch.tensor(t, device=device)
    ys_in[:, 0] = model.sos
    memory = encoded.unsqueeze(0).expand(n, -1, -1)
    mask = subsequent_mask(longest + 1, device=device).unsqueeze(0)
    logits, _ = model.decoder(ys_in, mask, memory, None)
    logp = torch.log_softmax(logits, dim=-1)
    att = []
    for i, (_, t) in enumerate(usable):
        target = torch.tensor(t + [eos], device=device)
        att.append(logp[i, :len(target)].gather(1, target.unsqueeze(1)).sum())
    att = torch.stack(att)
    # CTC: log P(tokens | video) over all alignments
    ctc_logp = model.ctc.log_softmax(encoded.unsqueeze(0)).transpose(0, 1).expand(-1, n, -1).contiguous()
    targets = torch.cat([torch.tensor(t, device=device) for _, t in usable])
    ctc = -torch.nn.functional.ctc_loss(
        ctc_logp, targets, torch.full((n,), encoded.shape[0], dtype=torch.long),
        torch.tensor([len(t) for _, t in usable], dtype=torch.long), blank=0, reduction='none', zero_infinity=True)
    scores = (1 - ctc_weight) * att + ctc_weight * ctc
    # Average per token (+<eos>): a raw sum always favours the shortest phrase ("No", "Yes").
    lengths = torch.tensor([len(t) + 1 for _, t in usable], device=device, dtype=scores.dtype)
    scores = scores / lengths
    return sorted(((p, float(s)) for (p, _), s in zip(usable, scores)), key=lambda x: -x[1])


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
        # Use the NVIDIA GPU when the CUDA build of PyTorch can see one; AVSR_DEVICE=cpu forces CPU.
        device = os.environ.get('AVSR_DEVICE') or ('cuda:0' if torch.cuda.is_available() else 'cpu')
        pipeline = InferencePipeline(os.environ['AVSR_CONFIG'], detector='mediapipe', face_track=True, device=device)
        vocab = {token: index for index, token in enumerate(pipeline.model.token_list)}
        emit({'type': 'ready', 'startup_ms': round((time.monotonic() - started) * 1000), 'device': device})
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
                    encoded = pipeline.model.model.encode(data.to(device))
                    if job.get('phrases'):
                        # Closed-set mode: rank the given phrases instead of free decoding.
                        ranked = score_phrases(pipeline.model.model, encoded, job['phrases'][:80], vocab)
                        if not ranked:
                            raise ValueError('no scorable phrases')
                        emit({'id': job_id, 'text': ranked[0][0], 'candidates': [p for p, _ in ranked[:3]],
                              'phrase_scores': [[p, round(s, 2)] for p, s in ranked[:5]],
                              'inference_ms': round((time.monotonic() - before) * 1000)})
                        continue
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
