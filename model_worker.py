"""Own one long-lived model process; keep neural dependencies out of the web server."""
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time
import uuid


class ModelUnavailable(Exception):
    pass


class PersistentModel:
    def __init__(self, root=None, command=None):
        self.root = Path(root or Path(__file__).resolve().parent)
        self.command = command
        self.process = None
        self.state = 'cold'
        self.active_job = None
        self.startup_ms = None
        self.last_latency_ms = None
        self.completed = 0
        self.message = ''
        self.lock = threading.RLock()
        self.request_lock = threading.Lock()
        self.ready = threading.Event()
        self.responses = queue.Queue()

    @property
    def configured(self):
        return bool(self.command) or all(os.environ.get(k) for k in ('AVSR_PYTHON', 'AVSR_REPO', 'AVSR_CONFIG'))

    def snapshot(self):
        with self.lock:
            return {'status': self.state, 'loaded': self.ready.is_set() and self.state in ('ready', 'processing'),
                    'startup_ms': self.startup_ms, 'last_latency_ms': self.last_latency_ms,
                    'completed': self.completed, 'device': 'CPU', 'message': self.message}

    def start(self):
        with self.lock:
            if not self.configured:
                raise ModelUnavailable('The visual model is not installed. Use Quick Phrases or run the model setup script.')
            if self.process and self.process.poll() is None:
                return self.snapshot()
            self.ready.clear()
            self.responses = queue.Queue()
            self.state = 'loading'
            self.message = 'Loading the visual model once for this session.'
            command = self.command or [os.environ['AVSR_PYTHON'], '-u', str(self.root / 'adapters' / 'avsr_worker.py')]
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env.setdefault('OMP_NUM_THREADS', '4')
            env.setdefault('MPLCONFIGDIR', str(self.root / 'vendor' / 'matplotlib-cache'))
            try:
                process = subprocess.Popen(command, cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, bufsize=1,
                                           start_new_session=(os.name != 'nt'), env=env)
            except OSError:
                self.state = 'error'
                raise ModelUnavailable('The visual model could not start. Check its configured Python environment.')
            self.process = process
            threading.Thread(target=self._read, args=(process,), daemon=True).start()
            # Drain diagnostics so verbose native libraries cannot block inference.
            def drain():
                for _ in process.stderr:
                    pass
            threading.Thread(target=drain, daemon=True).start()
            return self.snapshot()

    def _read(self, process):
        try:
            for line in process.stdout:
                if not line.startswith('UNMUTE_JSON:'):
                    continue
                try:
                    message = json.loads(line[len('UNMUTE_JSON:'):])
                except ValueError:
                    continue
                with self.lock:
                    if process is not self.process:
                        return
                    if message.get('type') == 'ready':
                        self.state = 'ready'
                        self.startup_ms = message.get('startup_ms')
                        self.message = 'Visual model ready; weights stay loaded.'
                        self.ready.set()
                    elif message.get('type') == 'startup_error':
                        self.state = 'error'
                        self.message = 'The visual model could not load. Check the model installation.'
                        self.ready.set()
                    else:
                        self.responses.put(message)
        finally:
            with self.lock:
                if process is self.process and self.state not in ('cold', 'stopped'):
                    self.state = 'error'
                    self.message = 'The visual worker stopped. Start a new attempt to reload it.'
                    self.ready.set()

    def infer(self, path, job_id=None, trim_start=0, duration=None, timeout=120):
        if not self.request_lock.acquire(blocking=False):
            raise ModelUnavailable('Another phrase is processing. Please wait for its review screen.')
        job_id = job_id or str(uuid.uuid4())
        started = time.monotonic()
        try:
            self.start()
            with self.lock:
                self.active_job = job_id
            if not self.ready.wait(timeout=timeout):
                self.cancel(job_id)
                raise ModelUnavailable('The visual model took too long to load. Try a quick phrase, then start again.')
            with self.lock:
                if self.active_job != job_id or self.state not in ('ready',):
                    raise ModelUnavailable(self.message or 'This attempt was canceled.')
                self.state = 'processing'
                self.message = 'Reading your silent video.'
                self.process.stdin.write(json.dumps({'id': job_id, 'path': str(path),
                                                     'trim_start': trim_start, 'duration': duration}) + '\n')
                self.process.stdin.flush()
            deadline = started + timeout
            while time.monotonic() < deadline:
                with self.lock:
                    if self.active_job != job_id:
                        raise ModelUnavailable('This attempt was canceled.')
                    if self.state == 'error':
                        raise ModelUnavailable(self.message)
                try:
                    response = self.responses.get(timeout=min(.25, max(.01, deadline - time.monotonic())))
                except queue.Empty:
                    continue
                if response.get('id') != job_id:
                    continue
                if response.get('error'):
                    messages = {
                        'no_face': 'Your whole face needs to be visible. Add front lighting, face the camera, and try again.',
                        'bad_video': 'This clip could not be read. Keep the camera active and try again.',
                    }
                    raise ModelUnavailable(messages.get(response['error'], 'The visual model could not read this phrase. Try again or choose a quick phrase.'))
                self.last_latency_ms = round((time.monotonic() - started) * 1000)
                self.completed += 1
                return {**response, 'total_ms': self.last_latency_ms}
            self.cancel(job_id)
            raise ModelUnavailable('Lip reading took too long. The attempt was stopped; you can try again.')
        except (BrokenPipeError, OSError):
            self.cancel(job_id)
            raise ModelUnavailable('The visual worker disconnected. Please try again.')
        finally:
            with self.lock:
                if self.active_job == job_id:
                    self.active_job = None
                    if self.process and self.process.poll() is None and self.state == 'processing':
                        self.state = 'ready'
                        self.message = 'Ready for the next phrase.'
            self.request_lock.release()

    def cancel(self, job_id):
        with self.lock:
            if self.active_job != job_id:
                return False
            self.active_job = None
            self._stop()
            return True

    def _stop(self):
        process = self.process
        self.process = None
        self.state = 'cold'
        self.message = 'Stopped. The next attempt will reload the model.'
        self.ready.set()  # Wake a loading request so cancellation returns promptly.
        if process and process.poll() is None:
            try:
                if os.name == 'nt':
                    process.terminate()
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    if os.name == 'nt': process.kill()
                    else: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
        if process:
            for stream in (process.stdin, process.stdout, process.stderr):
                try: stream.close()
                except (OSError, ValueError): pass

    def close(self):
        with self.lock:
            self.active_job = None
            self._stop()
