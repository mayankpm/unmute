export class FaceTracker extends EventTarget {
  constructor() { super(); this.active = false; this.pending = false; }
  async start(video) {
    this.video = video;
    this.active = true;
    this.suspended = false;
    this.worker = new Worker('/face-worker.js');
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Mouth tracking took too long to load. Try Record once.')), 30000);
      this.cancelInit = () => { clearTimeout(timer); reject(new DOMException('Tracking stopped.', 'AbortError')); };
      this.worker.onerror = () => { clearTimeout(timer); reject(new Error('Mouth tracking is unavailable. Try Record once.')); };
      this.worker.onmessage = event => {
        if (event.data.type === 'ready') { clearTimeout(timer); this.cancelInit = null; resolve(); }
        else if (event.data.type === 'error') { clearTimeout(timer); reject(new Error(event.data.message)); }
        else if (event.data.type === 'geometry') {
          this.pending = false;
          this.dispatchEvent(new CustomEvent('geometry', {detail: event.data}));
        }
      };
      this.worker.postMessage({type: 'init'});
    });
    if (!this.active) return;
    this.timer = setInterval(async () => {
      if (this.pending || this.suspended || !this.video.videoWidth || this.video.paused || !this.active) return;
      this.pending = true;
      try {
        const bitmap = await createImageBitmap(this.video);
        if (!this.active) { bitmap.close(); this.pending = false; return; }
        this.worker.postMessage({type: 'frame', bitmap, timestamp: performance.now()}, [bitmap]);
      } catch { this.pending = false; }
    }, 120);
  }
  stop() {
    this.active = false;
    this.cancelInit?.(); this.cancelInit = null;
    clearInterval(this.timer);
    this.worker?.terminate();
    this.pending = false;
  }
}

/* Geometry-only segmentation: never interprets mouth movement as words. */
export class MouthActivity {
  constructor() { this.reset(); }
  reset() { this.previous = null; this.hits = 0; this.started = null; this.lastMotion = null; }
  update(frame, time) {
    if (!frame.faceFound) { this.reset(); return {valid: false, moving: false}; }
    const face = frame.face;
    const valid = face.right - face.left >= .16 && face.right - face.left <= .85 &&
      face.top >= .01 && face.bottom <= .99 && frame.yaw < .45;
    if (!valid) { this.reset(); return {valid: false, moving: false}; }
    let motion = 0, headMotion = 0;
    if (this.previous) {
      motion = Math.abs(frame.openness - this.previous.openness) + Math.abs(frame.widthRatio - this.previous.widthRatio) * .4;
      headMotion = Math.hypot(frame.center.x - this.previous.center.x, frame.center.y - this.previous.center.y);
    }
    this.previous = frame;
    const moving = motion > .018 && headMotion < .035;
    this.hits = moving ? this.hits + 1 : Math.max(0, this.hits - 1);
    if (this.started === null && this.hits >= 2) { this.started = time - 120; this.lastMotion = time; }
    if (moving && this.started !== null) this.lastMotion = time;
    const complete = this.started !== null && time - this.started >= 1400 &&
      (time - this.lastMotion >= 850 || time - this.started >= 6500);
    return {valid, moving, active: this.started !== null, started: this.started, complete,
            headMoving: headMotion >= .035};
  }
}
