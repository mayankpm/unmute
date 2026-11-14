/* Experimental, speaker-specific visual template matching. No pretrained weights. */
export function frameDistance(a, b) {
  if (!a.length || a.length !== b.length) throw new Error('Incompatible features');
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += (a[i] - b[i]) ** 2;
  return sum / a.length;
}

export function dtw(a, b) {
  if (!a.length || !b.length) return Infinity;
  let previous = new Float64Array(b.length + 1).fill(Infinity);
  previous[0] = 0;
  for (let i = 1; i <= a.length; i++) {
    const current = new Float64Array(b.length + 1).fill(Infinity);
    for (let j = 1; j <= b.length; j++) {
      current[j] = frameDistance(a[i - 1], b[j - 1]) + Math.min(previous[j], current[j - 1], previous[j - 1]);
    }
    previous = current;
  }
  return previous[b.length] / (a.length + b.length);
}

export function rankTemplates(frames, samples) {
  const byPhrase = new Map();
  for (const sample of samples) {
    const distance = dtw(frames, sample.frames);
    const values = byPhrase.get(sample.phrase) || [];
    values.push(distance);
    byPhrase.set(sample.phrase, values);
  }
  return [...byPhrase].map(([phrase, values]) => {
    values.sort((a, b) => a - b);
    return {phrase, distance: values.slice(0, 2).reduce((s, n) => s + n, 0) / Math.min(values.length, 2)};
  }).sort((a, b) => a.distance - b.distance);
}

export function crossValidate(samples) {
  const eligible = samples.filter(s => samples.filter(other => other.phrase === s.phrase).length >= 2);
  if (new Set(eligible.map(s => s.phrase)).size < 2) return null;
  let correct = 0;
  for (const sample of eligible) {
    const ranked = rankTemplates(sample.frames, eligible.filter(other => other.id !== sample.id));
    if (ranked[0]?.phrase === sample.phrase) correct++;
  }
  return {correct, total: eligible.length};
}

export class VisualRecognizer {
  constructor() {
    this.samples = [];
    this.canvas = document.createElement('canvas');
    this.canvas.width = 16;
    this.canvas.height = 10;
    this.ctx = this.canvas.getContext('2d', {willReadFrequently: true});
    this.roi = {x: .5, y: .64, w: .32, h: .20};
  }

  async open() {
    this.db = await new Promise((resolve, reject) => {
      const request = indexedDB.open('unmute-visual-v1', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('samples', {keyPath: 'id'});
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    this.samples = await this.operation('readonly', store => store.getAll());
  }

  operation(mode, fn) {
    return new Promise((resolve, reject) => {
      const tx = this.db.transaction('samples', mode);
      const request = fn(tx.objectStore('samples'));
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error('Storage transaction aborted'));
    });
  }

  async add(phrase, frames) {
    const sample = {id: crypto.randomUUID(), phrase, frames, created: new Date().toISOString()};
    await this.operation('readwrite', store => store.put(sample));
    this.samples.push(sample);
  }

  async remove(phrase) {
    const remove = this.samples.filter(s => s.phrase === phrase);
    for (const sample of remove) await this.operation('readwrite', store => store.delete(sample.id));
    this.samples = this.samples.filter(s => s.phrase !== phrase);
  }

  feature(video) {
    const {x, y, w, h} = this.roi;
    this.ctx.drawImage(video, (x - w / 2) * video.videoWidth, (y - h / 2) * video.videoHeight,
      w * video.videoWidth, h * video.videoHeight, 0, 0, 16, 10);
    const pixels = this.ctx.getImageData(0, 0, 16, 10).data;
    const gray = [];
    for (let i = 0; i < pixels.length; i += 4) gray.push((pixels[i] * .299 + pixels[i + 1] * .587 + pixels[i + 2] * .114) / 255);
    const mean = gray.reduce((s, n) => s + n, 0) / gray.length;
    const std = Math.max(.04, Math.sqrt(gray.reduce((s, n) => s + (n - mean) ** 2, 0) / gray.length));
    return {values: gray.map(n => Math.round(((n - mean) / std) * 1000) / 1000), light: mean};
  }

  async capture(video, onProgress, duration = 3000) {
    if (!video.videoWidth || video.paused) throw new Error('Start your camera first.');
    const frames = [];
    const start = performance.now();
    let light = 0;
    while (performance.now() - start < duration) {
      const feature = this.feature(video);
      frames.push(feature.values);
      light += feature.light;
      onProgress(Math.min(1, (performance.now() - start) / duration));
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    onProgress(1);
    if (frames.length < 12) throw new Error('Too few camera frames. Please try again.');
    if (light / frames.length < .08) throw new Error('The mouth region is too dark. Add light and try again.');
    const motion = frames.slice(1).reduce((s, frame, i) => s + frameDistance(frame, frames[i]), 0) / (frames.length - 1);
    if (motion < .002) throw new Error('No clear mouth movement captured. Reposition the guide and try again.');
    return frames;
  }

  classify(frames) {
    const ranked = rankTemplates(frames, this.samples);
    const distinct = new Set(this.samples.map(s => s.phrase)).size;
    if (distinct < 2) throw new Error('Teach at least two different phrases before recognition.');
    // Distances are not confidence probabilities. Poor matches are explicitly rejected.
    if (ranked[0].distance > .85) throw new Error('No close visual match. Try again or choose a quick phrase.');
    return ranked.slice(0, 3);
  }
}
