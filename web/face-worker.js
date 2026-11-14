/* MediaPipe runs off the UI thread. Only geometry is returned to the page. */
let landmarker = null;
self.onmessage = async event => {
  const {type, bitmap, timestamp} = event.data;
  if (type === 'init') {
    try {
      const {FaceLandmarker, FilesetResolver} = await import('/assets/vision/vision_bundle.mjs');
      const files = await FilesetResolver.forVisionTasks('/assets/vision/wasm');
      landmarker = await FaceLandmarker.createFromOptions(files, {
        baseOptions: {modelAssetPath: '/assets/vision/face_landmarker.task', delegate: 'CPU'},
        runningMode: 'VIDEO', numFaces: 1, outputFaceBlendshapes: false,
        minFaceDetectionConfidence: .6, minFacePresenceConfidence: .6, minTrackingConfidence: .6
      });
      self.postMessage({type: 'ready'});
    } catch {
      self.postMessage({type: 'error', message: 'Automatic mouth tracking could not load. You can still record once or use quick phrases.'});
    }
    return;
  }
  if (type !== 'frame' || !bitmap) return;
  try {
    const result = landmarker.detectForVideo(bitmap, timestamp);
    const points = result.faceLandmarks[0];
    if (!points) { self.postMessage({type: 'geometry', faceFound: false, timestamp}); return; }
    const distance = (a, b) => Math.hypot((a.x - b.x) * bitmap.width, (a.y - b.y) * bitmap.height);
    const mouthWidth = distance(points[61], points[291]);
    const eyeWidth = distance(points[33], points[263]);
    const xs = points.map(p => p.x), ys = points.map(p => p.y);
    const mouth = {x: (points[61].x + points[291].x) / 2, y: (points[13].y + points[14].y) / 2,
                   w: Math.abs(points[61].x - points[291].x) * 1.6,
                   h: Math.max(.06, Math.abs(points[13].y - points[14].y) * 2.5)};
    self.postMessage({type: 'geometry', faceFound: true, timestamp,
      openness: distance(points[13], points[14]) / Math.max(1, mouthWidth),
      widthRatio: mouthWidth / Math.max(1, eyeWidth), mouth,
      face: {left: Math.min(...xs), right: Math.max(...xs), top: Math.min(...ys), bottom: Math.max(...ys)},
      center: {x: points[1].x, y: points[1].y},
      yaw: Math.abs(points[1].x - (points[33].x + points[263].x) / 2) / Math.max(.01, Math.abs(points[33].x - points[263].x))});
  } catch {
    self.postMessage({type: 'geometry', faceFound: false, timestamp});
  } finally { bitmap.close(); }
};
