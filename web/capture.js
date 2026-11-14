/* Bounded in-memory silent video. No files are persisted by this module. */
export class ClipRecorder {
  constructor(stream) {
    if (typeof MediaRecorder === 'undefined') throw new Error('Video recording needs desktop Chrome or Edge.');
    this.mime = ['video/webm;codecs=vp8', 'video/webm', 'video/mp4'].find(type => MediaRecorder.isTypeSupported(type));
    if (!this.mime) throw new Error('This browser cannot record silent video. Use a quick phrase.');
    this.recorder = new MediaRecorder(stream, {mimeType: this.mime, videoBitsPerSecond: 1200000});
    this.chunks = [];
    this.bytes = 0;
    this.settled = false;
    this.started = 0;
    this.done = new Promise((resolve, reject) => { this.resolve = resolve; this.reject = reject; });
    this.done.catch(() => {}); // A silent buffer may be discarded before anyone awaits it.
    this.recorder.ondataavailable = event => {
      if (event.data.size) { this.chunks.push(event.data); this.bytes += event.data.size; }
      if (this.bytes > 8 * 1024 * 1024) this.fail(new Error('The clip is too large. Try a shorter phrase.'));
    };
    this.recorder.onerror = () => this.fail(new Error('The browser could not record this clip. Please try again.'));
    this.recorder.onstop = () => {
      if (this.settled) return;
      const blob = new Blob(this.chunks, {type: this.mime});
      if (!blob.size) return this.fail(new Error('No video was captured. Please check the camera.'));
      this.settled = true;
      this.cleanup();
      this.resolve(blob);
    };
  }
  start() {
    this.started = performance.now();
    try { this.recorder.start(200); }
    catch { this.fail(new Error('The camera could not start recording. Please try again.')); }
    return this;
  }
  cleanup() {
    clearTimeout(this.finalizeTimer);
    this.recorder.ondataavailable = this.recorder.onerror = this.recorder.onstop = null;
  }
  fail(error) {
    if (this.settled) return;
    this.settled = true;
    this.cleanup();
    try { if (this.recorder.state !== 'inactive') this.recorder.stop(); } catch { /* disconnected camera */ }
    this.chunks = [];
    this.reject(error);
  }
  stop() {
    if (!this.settled && !this.finalizeTimer) {
      this.finalizeTimer = setTimeout(() => this.fail(new Error('The browser could not finish saving the recording. Please try again or use a quick phrase.')), 6000);
      try { if (this.recorder.state !== 'inactive') this.recorder.stop(); }
      catch { this.fail(new Error('The browser could not finish saving the recording. Please try again.')); }
    }
    return this.done;
  }
  abort() { this.fail(new DOMException('This attempt was canceled.', 'AbortError')); }
}

export async function blobData(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    const timer = setTimeout(() => { reader.abort(); reject(new Error('The browser could not prepare the video. Please try again.')); }, 8000);
    reader.onload = () => { clearTimeout(timer); resolve(String(reader.result).split(',')[1]); };
    reader.onerror = () => { clearTimeout(timer); reject(new Error('The browser could not read the video.')); };
    reader.readAsDataURL(blob);
  });
}
