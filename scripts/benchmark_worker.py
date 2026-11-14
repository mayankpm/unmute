"""Measure cold/warm execution on the same silent sample; not an accuracy test."""
import json
import argparse
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import load_env
from model_worker import PersistentModel


def main():
    load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--report',default='artifacts/worker-benchmark.json')
    args = parser.parse_args()
    if args.config:
        os.environ['AVSR_CONFIG'] = str((ROOT/args.config).resolve())
    clip = ROOT / 'artifacts' / 'upstream-visual-sample.mp4'
    if not clip.exists():
        raise SystemExit('Run scripts/check_model.py first to prepare the upstream sample.')
    worker = PersistentModel(ROOT)
    results = []
    try:
        for label in ['cold', 'warm', 'warm']:
            before = time.monotonic()
            result = worker.infer(clip, timeout=120)
            results.append({'run': label, 'ms': round((time.monotonic() - before) * 1000),
                            'transcript': result['text'], 'visual_candidates': result['candidates']})
            print(json.dumps(results[-1]), flush=True)
        report = {'sample': 'upstream sample, 3 seconds, no audio', 'results': results,
                  'worker': worker.snapshot(), 'accuracy': 'not measured on a new speaker'}
        (ROOT / args.report).write_text(json.dumps(report, indent=2))
    finally:
        worker.close()


if __name__ == '__main__':
    main()
