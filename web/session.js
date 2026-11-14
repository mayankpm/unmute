import {ClipRecorder} from './capture.js';
import {FaceTracker, MouthActivity} from './tracker.js';

export class CommunicationSession extends EventTarget {
  constructor(video, onClip) {
    super(); this.video = video; this.onClip = onClip;
    this.tracker = new FaceTracker(); this.activity = new MouthActivity();
    this.active = false; this.paused = false; this.modelReady = false;
    this.tracker.addEventListener('geometry', event => this.frame(event.detail));
  }
  state(phase, message, geometry = null) {
    this.dispatchEvent(new CustomEvent('state', {detail: {phase, message, geometry}}));
  }
  async start() {
    const generation = (this.generation || 0) + 1; this.generation = generation;
    this.active = true; this.paused = false; this.modelReady = false;
    this.state('loading', 'Getting your communication session ready…');
    try { await this.tracker.start(this.video); }
    catch (error) { if (generation === this.generation) this.stop(); throw error; }
  }
  ready() {
    this.modelReady = true;
    this.state(this.paused ? 'paused' : 'ready', this.paused
      ? 'Ready when you are. Resume capture to continue.'
      : 'Face the camera. Mouth a phrase whenever you’re ready.');
  }
  discard() { this.buffer?.abort(); this.buffer = null; this.activity.reset(); }
  pause(message = 'Review your words. Capture is paused until your next phrase.') {
    this.paused = true; this.tracker.suspended = true; this.discard();
    if (this.active) this.state('review', message);
  }
  resume() {
    this.discard(); this.paused = false; this.tracker.suspended = false; this.cooldown = performance.now() + 1000;
    if (this.active) this.state('ready', 'Ready for your next phrase.');
  }
  stop() {
    this.generation = (this.generation || 0) + 1;
    this.active = false; this.paused = false; this.modelReady = false;
    this.tracker.stop(); this.discard(); this.state('stopped', 'Session ended.');
  }
  async finish(time) {
    if (!this.buffer || this.paused) return;
    const recorder = this.buffer;
    const trimStart = Math.max(0, (this.activity.started - recorder.started) / 1000 - .35);
    const duration = Math.min(8, (time - recorder.started) / 1000 - trimStart);
    this.buffer = null; this.paused = true; this.tracker.suspended = true; this.activity.reset();
    this.state('processing', 'Phrase captured. Finding your words…');
    try {
      const blob = await recorder.stop();
      if (this.active) await this.onClip(blob, {trim_start: trimStart, duration});
    } catch (error) {
      if (this.active && error.name !== 'AbortError') this.state('error', error.message || 'Please try another phrase.');
    }
  }
  frame(frame) {
    if (!this.active || !this.modelReady || this.paused) return;
    const time = performance.now();
    const movement = this.activity.update(frame, time);
    this.dispatchEvent(new CustomEvent('geometry', {detail: frame}));
    if (!movement.valid) {
      this.discard();
      this.state('position', frame.faceFound ? 'Keep your whole face visible and face the camera.' : 'Looking for your face. Move into view.');
      return;
    }
    if (time < (this.cooldown || 0)) return;
    if (!this.buffer) {
      try { this.buffer = new ClipRecorder(this.video.srcObject).start(); }
      catch (error) { this.pause(); this.state('error', error.message); return; }
    }
    if (movement.active) {
      this.state('capturing', 'Capturing your phrase. Pause naturally when you’re finished.');
      if (movement.complete) this.finish(time);
    } else {
      this.state('ready', movement.headMoving ? 'Keep your head still; move only your mouth.' : 'Ready. Mouth a phrase and pause when finished.');
      // Refresh silent buffers; only a short pre-roll is kept for a detected phrase.
      if (time - this.buffer.started > 8000) this.discard();
    }
  }
}
