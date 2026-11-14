import {VisualRecognizer, crossValidate} from './recognizer.js';
import {BedsideController} from './serial.js';
import {ClipRecorder, blobData} from './capture.js';
import {CommunicationSession} from './session.js';

const $ = id => document.getElementById(id);
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths = {
  voice:'M4 10v4m4-7v10m4-14v18m4-14v10m4-7v4',
  spark:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
  heart:'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z',
  chart:'M4 3v17h17M8 15v-3m5 3V7m5 8v-5',
  sliders:'M4 6h5m4 0h7M4 12h9m4 0h3M4 18h2m4 0h10M9 3v6m8 0v6M6 15v6',
  shield:'M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4Zm-4 9 3 3 5-6',
  camera:'M3 7h4l2-3h6l2 3h4v13H3V7Zm13 6a4 4 0 1 0-8 0 4 4 0 0 0 8 0',
  sun:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm0-6v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5',
  record:'M20 12a8 8 0 1 0-16 0 8 8 0 0 0 16 0Zm-5 0a3 3 0 1 0-6 0 3 3 0 0 0 6 0',
  volume:'m3 9 5 0 5-5v16l-5-5H3V9Zm13-1c3 2 3 6 0 8m3-11c5 4 5 10 0 14',
  bell:'M5 17h14l-2-4V9a5 5 0 0 0-10 0v4l-2 4Zm5 3h4M12 2v2',
  keyboard:'M2 5h20v14H2V5Zm4 4h1m3 0h1m3 0h1m3 0h1M6 12h1m3 0h1m3 0h1m3 0h1M7 16h10',
  usb:'M12 21V3m-3 3 3-3 3 3M12 16l-6-4V9m6 4 6-4V6M4 7h4v3H4V7Zm12-4h4v3h-4V3Z',
  check:'m5 12 4 4L19 6',
  download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  water:'M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12Zm-4 12q0 4 4 4',
  pillow:'M3 7q9-4 18 0v11q-9-4-18 0V7Zm3 3h12',
  family:'M9 7a3 3 0 1 0-6 0 3 3 0 0 0 6 0Zm12 0a3 3 0 1 0-6 0 3 3 0 0 0 6 0M1 20v-4a5 5 0 0 1 10 0v4m2 0v-4a5 5 0 0 1 10 0v4',
  cold:'M12 2v20M3 7l18 10M3 17 21 7M9 3l3 3 3-3M9 21l3-3 3 3M3 10l4-1V5m14 9-4 1v4M3 14l4 1v4m14-9-4-1V5',
  care:'M9 3h6v6h6v6h-6v6H9v-6H3V9h6V3Z',
  smile:'M21 12a9 9 0 1 0-18 0 9 9 0 0 0 18 0ZM8 9h.01M16 9h.01M7 14q5 7 10 0',
};
function icon(name) { return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.voice}"/></svg>`; }
document.querySelectorAll('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));
const phraseIcons = {water:'water',pain:'heart',nurse:'bell',family:'family',cold:'cold',hot:'sun',pillow:'pillow',toilet:'care',sick:'care',breath:'voice',scared:'heart',thanks:'smile'};
const sourceNames = {quick:'Quick phrase',typed:'Typed / local suggestion',gemini:'Gemini text suggestion','local-visual':'Local visual template','auto-avsr':'Auto-AVSR',demo:'Simulated demo','help-button':'Direct help button',edited:'Patient-corrected words'};
const recognizer = new VisualRecognizer();
const bedside = new BedsideController();
let config = {phrases: []}, state = {requests: [], memory: [], metrics: {}, profile: {}}, currentView = 'patient';
let stream = null, busy = false, sending = false, decision = null, choice = null, sent = null, capturedBlob = null;
let filter = 'All', scanIndex = -1, scanTimer = null, scanInterval = 2200, toastTimer, pollInFlight = false;
let backendOnline = false, lastHardwareState = '', lastHardwareSent = 0, lastHelp = 0, lastConfirmedFrames = null;
let processingTimer = null;
let activeRecorder = null, activeRequest = null, activeJob = null, attemptGeneration = 0, sessionGeneration = 0;
let selectedWord = 0, evaluationDecision = null, lastTiming = null;
const communication = new CommunicationSession($('camera'), (blob, bounds) => processSessionClip(blob, bounds));
const patientGrid = document.querySelector('.patient-grid');
const cameraCard = document.querySelector('.camera-card');
const teachGrid = document.querySelector('.teach-grid');

function toast(message, error = false) {
  $('toast').textContent = message;
  $('toast').classList.toggle('error', error);
  $('toast').classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('toast').classList.add('hidden'), error ? 8000 : 4500);
}
async function api(path, data, signal) {
  const headers = {'Content-Type':'application/json'};
  const token = sessionStorage.getItem('unmute-token');
  if (token) headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(path, {method: data === undefined ? 'GET' : 'POST', headers,
      body: data === undefined ? undefined : JSON.stringify(data), signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(path === '/api/transcribe' ? 150000 : 35000)]) : AbortSignal.timeout(path === '/api/transcribe' ? 150000 : 35000)});
  } catch (error) {
    if (error.name === 'TimeoutError') throw new Error(path === '/api/transcribe'
      ? 'Lip reading took too long. Your recording has stopped. Try a quick phrase or record again.'
      : 'The server took too long to respond. Please try again.');
    throw error;
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}
function guard(fn) {
  return async (...args) => { try { await fn(...args); } catch (error) { toast(error.message || 'Something went wrong. Please try again.', true); } };
}
function setView(view) {
  if (!['patient','teach','care','insights','settings'].includes(view)) view = 'patient';
  if (busy || sending) return toast('Please wait for the current recording or request.');
  if (view !== 'patient' && communication.active) endSession(view !== 'teach');
  currentView = view;
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('hidden', el.id !== `view-${view}`));
  document.querySelectorAll('[data-view]').forEach(el => {
    const active = el.dataset.view === view;
    el.classList.toggle('active', active);
    if (active) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current');
  });
  if (view === 'teach') teachGrid.prepend(cameraCard); else patientGrid.prepend(cameraCard);
  cameraCard.querySelector('.record-controls').classList.toggle('hidden', view === 'teach');
  document.querySelector('.teach-grid>.card:last-child').classList.add('training-progress');
  if (location.hash !== `#${view}`) history.replaceState(null, '', `#${view}`);
  clearScan();
  if ($('scan-toggle').checked) startScan();
  if (view === 'care') renderCare();
  if (view === 'insights') renderInsights();
  if (view === 'teach') renderTraining();
}
document.querySelectorAll('[data-view]').forEach(el => el.addEventListener('click', () => setView(el.dataset.view)));
document.querySelectorAll('[data-go]').forEach(el => el.addEventListener('click', () => setView(el.dataset.go)));
$('settings-shortcut').addEventListener('click', () => setView('settings'));
window.addEventListener('hashchange', () => setView(location.hash.slice(1)));

function updateProfile(profile) {
  $('sidebar-name').textContent = profile.name;
  $('sidebar-room').textContent = profile.room;
  $('avatar').textContent = profile.name?.slice(0, 1).toUpperCase();
  $('profile-name').value = profile.name || 'Alex';
  $('profile-room').value = profile.room || 'Bed 01';
  $('profile-names').value = profile.names || '';
  $('profile-context').value = profile.context || '';
  scanInterval = profile.scan_ms || 2200;
  $('scan-speed').value = scanInterval;
  $('scan-speed-label').textContent = `${(scanInterval / 1000).toFixed(1)} seconds`;
}
function renderConnections() {
  const checks = config.integration_checks || {};
  $('gemini-note').textContent = config.gemini ? '(configured)' : '(key required)';
  $('gemini-toggle').disabled = !config.gemini;
  $('avsr-gemini').disabled = !config.gemini;
  $('integration-status').innerHTML = [
    ['Local storage', backendOnline ? 'SQLite · connected' : 'Server offline'],
    ['Visual phrases', `${recognizer.samples.length} local examples`],
    ['Gemini API', checks.gemini?.status === 'verified' ? `Live verified · ${checks.gemini.model}` : config.gemini ? 'Configured · not yet verified' : 'Not configured'],
    ['MongoDB Atlas', config.atlas || 'Not configured'],
    ['Auto-AVSR', config.avsr ? 'Configured · unverified' : 'Not configured'],
    ['Visual model worker', config.model_worker?.loaded ? 'Loaded · ready for reuse' : config.model_worker?.status || 'Not started'],
    ['Automatic mouth tracking', config.face_tracking ? 'Installed · browser only' : 'Run scripts/setup_vision.py'],
    ['USB controller', bedside.connected ? 'Connected' : 'Not connected']
  ].map(([name, value]) => `<div class="integration-row"><span>${escape(name)}</span><span>${escape(value)}</span></div>`).join('');
  $('integration-check-results').innerHTML = Object.values(checks).map(check => `<div class="integration-check ${check.status === 'verified' ? 'verified' : ''}"><strong>${check.service === 'gemini' ? 'Gemini' : 'MongoDB Atlas'} · ${escape(check.status.replaceAll('_',' '))}</strong><p>${escape(check.message)}</p>${check.candidates ? `<p>Test suggestions: ${check.candidates.map(escape).join(' / ')}</p>` : ''}${check.document_count !== undefined ? `<p>${check.document_count} documents in the requests collection</p>` : ''}<small>Checked ${escape(new Date(check.checked_at).toLocaleTimeString())} · ${check.latency_ms} ms</small></div>`).join('');
}
for (const service of ['gemini','atlas']) {
  $(`check-${service}`).addEventListener('click', guard(async () => {
    const buttons = [$('check-gemini'),$('check-atlas')];
    buttons.forEach(button => button.disabled = true);
    $(`check-${service}`).textContent = 'Checking…';
    try {
      await api('/api/check-integration', {service});
      config = await api('/api/config');
      renderConnections();
    } finally {
      buttons.forEach(button => button.disabled = false);
      $('check-gemini').textContent = 'Test Gemini';
      $('check-atlas').textContent = 'Test Atlas';
    }
  }));
}
function renderPhrases() {
  const phrases = config.phrases.filter(p => filter === 'All' || p.category === filter);
  $('quick-phrases').innerHTML = phrases.map(p => `<button class="phrase-button" data-phrase="${escape(p.id)}"><span class="phrase-icon">${icon(phraseIcons[p.id])}</span><span>${escape(p.text)}</span><span class="arrow">↗</span></button>`).join('');
  $('quick-phrases').querySelectorAll('[data-phrase]').forEach(el => el.addEventListener('click', guard(() => chooseQuick(el.dataset.phrase))));
  if ($('scan-toggle').checked) startScan();
}
document.querySelectorAll('[data-filter]').forEach(el => el.addEventListener('click', () => {
  filter = el.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(button => button.classList.toggle('active', button === el));
  renderPhrases();
}));
async function chooseQuick(id) {
  if (busy || sending) return;
  const response = await api('/api/choices', {source:'quick', phrase_id:id});
  showDecision(response);
  selectChoice(0);
}
function hideInterpretation() {
  ['interpretation-empty','choice-panel','sent-panel'].forEach(id => $(id).classList.add('hidden'));
}
function resetInteraction() {
  if (sending) return;
  decision = null; choice = null; sent = null; lastConfirmedFrames = null;
  hideInterpretation();
  $('interpretation-empty').classList.remove('hidden');
  $('confirmation').classList.add('hidden');
  $('interpret-badge').textContent = 'You’re in control';
  $('evaluation-panel').classList.add('hidden');
  evaluationDecision = null;
  if (communication.active) communication.resume();
  startScanIfEnabled();
}
function showDecision(response) {
  if (communication.active) communication.pause();
  decision = response; choice = null; sent = null;
  hideInterpretation();
  $('choice-panel').classList.remove('hidden');
  $('confirmation').classList.add('hidden');
  $('word-editor').classList.add('hidden');
  $('confirm-button').disabled = false;
  $('candidate-question').textContent = response.question || 'Which sentence did you mean?';
  $('raw-transcript').textContent = response.raw ? `Raw transcript: “${response.raw}”` : '';
  $('raw-transcript').classList.toggle('hidden', !response.raw);
  $('candidate-source').textContent = `${sourceNames[response.source] || response.source}${response.model ? ` · ${response.model}` : ''}${response.simulated ? ' · Sample words, not camera recognition' : ' · Suggestions require your confirmation'}`;
  $('interpret-badge').textContent = response.simulated ? 'Demo mode' : 'Review your words';
  evaluationDecision = (['auto-avsr','local-visual'].includes(response.source) || (response.source === 'gemini' && response.timing)) && !response.simulated ? response.decision_id : null;
  $('evaluation-panel').classList.toggle('hidden', !evaluationDecision);
  $('evaluation-feedback').textContent = 'Enter the exact words you intended to say to measure this attempt.';
  $('attempt-timing').classList.toggle('hidden', !response.timing);
  if (response.timing) {
    lastTiming = response.timing;
    $('attempt-timing').textContent = `${(response.timing.total_ms/1000).toFixed(1)}s to suggestions · ${(response.timing.inference_ms/1000).toFixed(1)}s visual model${response.gemini_used ? ` + ${(response.timing.gemini_ms/1000).toFixed(1)}s Gemini` : ''}`;
  }
  $('candidates').innerHTML = response.candidates.map((text, index) => `<button class="candidate" data-choice="${index}" aria-pressed="false"><span class="candidate-number">${index + 1}</span><span>${escape(text)}</span></button>`).join('');
  $('candidates').querySelectorAll('[data-choice]').forEach(el => el.addEventListener('click', () => selectChoice(Number(el.dataset.choice))));
  if (response.warning) toast(response.warning, true);
  startScanIfEnabled();
}
function selectChoice(index) {
  if (sending || !decision || !decision.candidates[index]) return;
  choice = index;
  document.querySelectorAll('.candidate').forEach((el, i) => {el.classList.toggle('selected', i === index); el.setAttribute('aria-pressed', String(i === index));});
  $('selected-text').textContent = decision.candidates[index];
  $('confirmation').classList.remove('hidden');
  $('word-editor').classList.add('hidden');
  $('confirm-button').disabled = false;
  $('candidate-question').textContent = 'Ready to say this?';
  startScanIfEnabled();
}
$('back-button').addEventListener('click', () => {
  if (sending) return;
  choice = null;
  $('confirmation').classList.add('hidden');
  document.querySelectorAll('.candidate').forEach(el => {el.classList.remove('selected');el.setAttribute('aria-pressed','false');});
  $('candidate-question').textContent = decision?.question || 'Which sentence did you mean?';
  startScanIfEnabled();
});
$('none-button').addEventListener('click', resetInteraction);
$('new-button').addEventListener('click', resetInteraction);

async function confirmChoice() {
  if (sending || !decision || choice === null) return;
  sending = true;
  clearScan();
  $('confirm-button').disabled = true;
  try {
    const request = await api('/api/confirm', {decision_id:decision.decision_id, choice, confirmed:true});
    showSent(request);
    if ($('auto-speak').checked) speak(request.text);
    await poll();
  } finally {
    sending = false;
    $('confirm-button').disabled = false;
    startScanIfEnabled();
  }
}
$('confirm-button').addEventListener('click', guard(confirmChoice));
function showSent(request) {
  sent = request;
  decision = null; choice = null;
  hideInterpretation();
  $('sent-panel').classList.remove('hidden');
  $('sent-text').textContent = request.text;
  $('interpret-badge').textContent = request.simulated ? 'Demo mode' : 'Confirmed by you';
  updateSentStatus();
  $('save-phrase-button').textContent = 'Save to my phrases';
}
function updateSentStatus() {
  if (!sent) return;
  const current = state.requests.find(r => r.id === sent.id) || sent;
  const labels = {pending:'Sent · waiting for acknowledgment',acknowledged:'Acknowledged by the care team',resolved:'Marked resolved by the care team'};
  $('request-status').textContent = `${current.simulated ? 'Demo · ' : ''}${labels[current.status]}`;
}
function speak(text) {
  if (!('speechSynthesis' in window)) return toast('Speech is unavailable in this browser. Your message remains visible.', true);
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = Number($('speech-rate').value);
  const voice = speechSynthesis.getVoices().find(v => v.voiceURI === $('voice-select').value);
  if (voice) utterance.voice = voice;
  utterance.onerror = event => {if (event.error !== 'interrupted' && event.error !== 'canceled') toast('Speech could not play. The confirmed message is still saved.', true);};
  speechSynthesis.cancel();
  speechSynthesis.speak(utterance);
}
$('repeat-button').addEventListener('click', () => {if(sent) speak(sent.text);});

function renderWordChips() {
  const words = $('sentence-edit').value.trim().split(/\s+/);
  selectedWord = Math.max(0, Math.min(selectedWord, words.length - 1));
  $('word-chips').innerHTML = words.map((word, index) => `<button type="button" class="word-chip ${index === selectedWord ? 'selected' : ''}" data-word="${index}">${escape(word)}</button>`).join('');
  $('word-replacement').value = words[selectedWord] || '';
  $('word-chips').querySelectorAll('[data-word]').forEach(button => button.addEventListener('click', () => {
    selectedWord = Number(button.dataset.word); renderWordChips(); $('word-replacement').focus();
  }));
}
$('edit-toggle').addEventListener('click', () => {
  if (!decision || choice === null || sending) return;
  $('sentence-edit').value = decision.candidates[choice];
  selectedWord = 0; renderWordChips();
  $('word-editor').classList.remove('hidden');
  $('confirm-button').disabled = true;
});
$('edit-cancel').addEventListener('click', () => {
  $('word-editor').classList.add('hidden'); $('confirm-button').disabled = false;
});
$('word-edit-form').addEventListener('submit', event => {
  event.preventDefault();
  const words = $('sentence-edit').value.trim().split(/\s+/);
  words[selectedWord] = $('word-replacement').value.trim();
  $('sentence-edit').value = words.join(' '); renderWordChips();
});
$('sentence-edit-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  if (!decision || sending) return;
  const response = await api('/api/revise', {decision_id: decision.decision_id, text: $('sentence-edit').value});
  showDecision(response); selectChoice(0);
}));
$('evaluation-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  if (!evaluationDecision) return;
  const result = await api('/api/evaluate', {decision_id: evaluationDecision, reference: $('evaluation-reference').value});
  $('evaluation-feedback').textContent = `Raw model: ${result.raw.errors}/${result.raw.words} word errors (${Math.round(result.raw.wer*100)}% WER). Top suggestion: ${result.suggestion.errors}/${result.suggestion.words} (${Math.round(result.suggestion.wer*100)}% WER). Saved to Session insights.`;
  await poll();
}));

async function refreshPhrases() {
  config = await api('/api/config');
  state = await api('/api/state');
  renderPhrases(); renderFavorites();
}
function renderFavorites() {
  $('favorite-list').innerHTML = (state.favorites || []).map(phrase => `<div class="favorite-item"><span>${escape(phrase.text)}</span><button class="text-button" data-remove-phrase="${escape(phrase.id)}" aria-label="Remove ${escape(phrase.text)}">Remove</button></div>`).join('');
  $('favorite-list').querySelectorAll('[data-remove-phrase]').forEach(button => button.addEventListener('click', guard(async () => {
    await api('/api/favorites', {action:'remove', id:button.dataset.removePhrase}); await refreshPhrases();
  })));
}
$('favorite-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  await api('/api/favorites', {text:$('favorite-text').value});
  $('favorite-text').value = ''; await refreshPhrases(); toast('Your phrase is ready as a shortcut.');
}));
$('save-phrase-button').addEventListener('click', guard(async () => {
  if (!sent) return;
  await api('/api/favorites', {text:sent.text}); await refreshPhrases();
  $('save-phrase-button').textContent = 'Saved to my phrases'; toast('Saved. Your words are one selection away next time.');
}));
function populateVoices() {
  const selected = $('voice-select').value || localStorage.getItem('unmute-voice') || '';
  $('voice-select').innerHTML = '<option value="">System default</option>' + (window.speechSynthesis?.getVoices() || []).map(v => `<option value="${escape(v.voiceURI)}">${escape(v.name)} · ${escape(v.lang)}</option>`).join('');
  $('voice-select').value = selected;
}
if ('speechSynthesis' in window) speechSynthesis.addEventListener('voiceschanged', populateVoices);
populateVoices();
$('voice-select').addEventListener('change', () => localStorage.setItem('unmute-voice', $('voice-select').value));

$('demo-button').addEventListener('click', guard(async () => {
  if (busy || sending) return;
  lastConfirmedFrames = null;
  showDecision(await api('/api/choices', {source:'demo',candidates:['I need water','Call my daughter','Please adjust my pillow']}));
}));
$('typed-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  if (busy || sending) return;
  const button = event.currentTarget.querySelector('button[type=submit]');
  button.disabled = true;
  try {
    lastConfirmedFrames = null;
    const response = await api('/api/interpret', {raw:$('typed-input').value, use_gemini:$('gemini-toggle').checked});
    showDecision(response);
  } finally {button.disabled = false;}
}));
async function requestHelp() {
  if (sending || Date.now() - lastHelp < 3000) return;
  lastHelp = Date.now();
  await endSession(false);
  const request = await api('/api/help', {confirmed:true});
  showSent(request);
  if ($('auto-speak').checked) speak(request.text);
  toast('Help requested. Waiting for caregiver acknowledgment.');
  await poll();
}
$('help-button').addEventListener('click', guard(requestHelp));

function updateGuide() {
  const x = Number($('roi-x').value) / 100, y = Number($('roi-y').value) / 100, w = Number($('roi-size').value) / 100;
  recognizer.roi = {x:1 - x, y, w, h:w * .625}; // mirrored preview, unmirrored canvas coordinates
  const guide = $('mouth-guide');
  guide.style.left = `${(x - w / 2) * 100}%`;
  guide.style.top = `${(y - w * .625 / 2) * 100}%`;
  guide.style.width = `${w * 100}%`;
  guide.style.height = `${w * .625 * 100}%`;
  localStorage.setItem('unmute-roi', JSON.stringify({x:x * 100,y:y * 100,w:w * 100}));
}
try {
  const roi = JSON.parse(localStorage.getItem('unmute-roi') || 'null');
  if (roi) { $('roi-x').value = roi.x; $('roi-y').value = roi.y; $('roi-size').value = roi.w; }
} catch { /* default framing */ }
['roi-x','roi-y','roi-size'].forEach(id => $(id).addEventListener('input', updateGuide));
updateGuide();
$('align-toggle').addEventListener('click', () => $('alignment').classList.toggle('hidden'));
async function startCamera() {
  if (stream) return;
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera requires localhost or an HTTPS connection.');
  const cameraStream = await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},facingMode:'user'},audio:false});
  stream = cameraStream;
  const video = $('camera');
  video.srcObject = stream;
  await video.play();
  $('camera-stage').style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
  $('camera-placeholder').classList.add('hidden');
  ['mouth-guide','camera-live','camera-stop'].forEach(id => $(id).classList.remove('hidden'));
  $('camera-badge').textContent = 'Camera active';
  $('camera-badge').classList.add('green');
  $('camera-hint').textContent = 'Align your mouth inside the guide. Keep your head still.';
}
$('camera-start').addEventListener('click', guard(startCamera));
function stopCamera() {
  if (busy) return;
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  $('camera').srcObject = null;
  $('camera-placeholder').classList.remove('hidden');
  ['mouth-guide','camera-live','camera-stop'].forEach(id => $(id).classList.add('hidden'));
  $('camera-badge').textContent = 'Camera off';
  $('camera-badge').classList.remove('green');
}
$('camera-stop').addEventListener('click', guard(() => communication.active ? endSession(true) : stopCamera()));
async function countdown(phrase) {
  const dialog = $('countdown-dialog');
  $('countdown-phrase').textContent = phrase;
  dialog.showModal();
  for (let i = 3; i > 0; i--) {
    $('countdown-number').textContent = i;
    await new Promise(resolve => setTimeout(resolve, 650));
    if (!dialog.open) throw new Error('Recording canceled.');
  }
  dialog.close();
}
function captureProgress(progress) {
  $('capture-clock').textContent = `${Math.max(0, 3 - progress * 3).toFixed(1)}s`;
}
function capturePhase(phase, message) {
  clearInterval(processingTimer);
  processingTimer = null;
  $('capture-overlay').dataset.phase = phase;
  $('capture-message').textContent = message;
  if (phase === 'recording') {
    captureProgress(0);
    $('capture-clock').setAttribute('aria-label', 'Recording time remaining');
    $('camera-badge').textContent = 'Recording';
    $('camera-hint').textContent = 'Mouth your phrase once. Recording stops automatically after 3 seconds.';
  } else {
    const started = performance.now();
    const tick = () => { $('capture-clock').textContent = `${Math.floor((performance.now() - started) / 1000)}s elapsed`; };
    tick();
    processingTimer = setInterval(tick, 1000);
    $('capture-clock').setAttribute('aria-label', 'Processing elapsed time');
    $('camera-badge').textContent = 'Processing';
    $('camera-hint').textContent = 'Recording finished. You can relax while your words are processed.';
  }
}
async function captureVideo() {
  const recorder = new ClipRecorder(stream).start();
  activeRecorder = recorder;
  const started = performance.now();
  const interval = setInterval(() => captureProgress(Math.min(1, (performance.now() - started) / 3000)), 100);
  const stopTimer = setTimeout(() => {
    captureProgress(1);
    capturePhase('processing', 'Saving your recording…');
    recorder.stop();
  }, 3000);
  try { return await recorder.done; }
  finally {
    clearInterval(interval); clearTimeout(stopTimer);
    if (activeRecorder === recorder) activeRecorder = null;
  }
}

function setCaptureBusy(value) {
  busy = value;
  $('record-button').disabled = value;
  $('teach-record').disabled = value;
  $('camera-stop').disabled = value;
  $('recognition-mode').disabled = value || communication.active;
}

async function transcribeClip(blob, bounds, generation) {
  const controller = new AbortController();
  activeRequest = controller;
  const job = crypto.randomUUID();
  activeJob = job;
  capturePhase('processing', $('avsr-gemini').checked ? 'Reading your lips, then preparing Gemini suggestions…' : 'Reading your lips…');
  try {
    const video = await blobData(blob);
    if (generation !== attemptGeneration) throw new DOMException('Canceled', 'AbortError');
    const response = await api('/api/transcribe', {video, mime: blob.type, job_id: job,
      use_gemini: $('avsr-gemini').checked && !!config.gemini, ...bounds}, controller.signal);
    if (generation !== attemptGeneration) throw new DOMException('Canceled', 'AbortError');
    showDecision(response);
  } finally {
    if (activeRequest === controller) { activeRequest = null; activeJob = null; }
  }
}

async function cancelAttempt(pauseSession = true) {
  attemptGeneration++;
  activeRecorder?.abort(); activeRecorder = null;
  activeRequest?.abort(); activeRequest = null;
  const job = activeJob; activeJob = null;
  clearInterval(processingTimer); processingTimer = null;
  $('countdown-dialog').close();
  $('capture-overlay').classList.add('hidden');
  setCaptureBusy(false);
  $('camera-badge').textContent = stream ? 'Camera active' : 'Camera off';
  $('camera-hint').textContent = 'Attempt canceled. You can try again or choose a quick phrase.';
  if (pauseSession && communication.active) {
    communication.pause('Attempt canceled. Try another phrase when you’re ready.');
    $('session-retry').classList.remove('hidden');
  }
  if (job) await api('/api/model/cancel', {job_id: job}).catch(() => {});
}
$('capture-cancel').addEventListener('click', guard(() => cancelAttempt()));

async function processSessionClip(blob, bounds) {
  const generation = ++attemptGeneration;
  setCaptureBusy(true);
  $('capture-overlay').classList.remove('hidden');
  try {
    await transcribeClip(blob, bounds, generation);
  } catch (error) {
    if (error.name !== 'AbortError' && generation === attemptGeneration) {
      $('camera-hint').textContent = error.message;
      throw error;
    }
  } finally {
    if (generation === attemptGeneration) {
      clearInterval(processingTimer); processingTimer = null;
      $('capture-overlay').classList.add('hidden');
      setCaptureBusy(false);
      $('camera-badge').textContent = 'Camera active';
      startScanIfEnabled();
    }
  }
}

async function endSession(turnCameraOff = false) {
  sessionGeneration++;
  communication.stop();
  updateGuide(); $('mouth-guide').querySelector('span').textContent = 'ALIGN YOUR MOUTH';
  $('session-toggle').innerHTML = `${icon('voice')}Start communicating`;
  $('session-retry').classList.add('hidden');
  $('recognition-mode').disabled = false;
  if (busy || activeJob || activeRecorder) await cancelAttempt(false);
  if (turnCameraOff) stopCamera();
}

async function startSession() {
  if (!config.avsr) throw new Error('Install the visual model first, or use Record a phrase with taught examples.');
  if (!config.face_tracking) throw new Error('Run python3 scripts/setup_vision.py to install automatic mouth tracking.');
  const generation = ++sessionGeneration;
  communication.active = true;
  $('session-toggle').innerHTML = `${icon('record')}End session`;
  $('recognition-mode').value = 'avsr';
  $('recognition-mode').disabled = true;
  resetInteraction();
  $('session-status').textContent = 'Getting ready';
  $('session-detail').textContent = 'Preparing the camera and local models…';
  try {
    await startCamera();
    if (generation !== sessionGeneration) { if (!communication.active) stopCamera(); return; }
    await Promise.all([communication.start(), api('/api/model/warmup', {})]);
    const started = performance.now();
    while (generation === sessionGeneration) {
      const status = await api('/api/model/status');
      config.model_worker = status;
      if (status.status === 'ready') { communication.ready(); return; }
      if (status.status === 'error') throw new Error(status.message || 'The visual model could not load. Try a quick phrase.');
      if (performance.now() - started > 120000) throw new Error('The visual model took too long to load. Try a quick phrase.');
      $('session-status').textContent = 'Warming up your voice';
      $('session-detail').textContent = `Loading the visual model once · ${Math.floor((performance.now() - started) / 1000)}s. Quick phrase buttons remain available.`;
      await new Promise(resolve => setTimeout(resolve, 600));
    }
  } catch (error) {
    if (generation === sessionGeneration) { await endSession(false); throw error; }
  }
}
$('session-toggle').addEventListener('click', guard(() => communication.active ? endSession(true) : startSession()));
$('session-retry').addEventListener('click', () => {
  resetInteraction(); $('session-retry').classList.add('hidden'); communication.resume();
});
communication.addEventListener('state', event => {
  const {phase, message} = event.detail;
  document.querySelector('.session-panel').dataset.phase = phase;
  const labels = {loading:'Getting ready',ready:'Ready for your words',capturing:'Capturing your phrase',
    processing:'Finding your words',review:'Your words, your decision',position:'Adjust your position',error:'Let’s try again',paused:'Capture paused',stopped:'Session off'};
  $('session-status').textContent = labels[phase] || phase;
  $('session-detail').textContent = message;
  $('session-retry').classList.toggle('hidden', !['error','paused'].includes(phase));
});
communication.addEventListener('geometry', event => {
  const frame = event.detail;
  if (!frame.faceFound) return;
  const {x,y,w,h} = frame.mouth;
  const guide = $('mouth-guide');
  guide.style.left = `${(1 - x - w/2)*100}%`; guide.style.top = `${(y-h/2)*100}%`;
  guide.style.width = `${w*100}%`; guide.style.height = `${h*100}%`;
  guide.querySelector('span').textContent = 'MOUTH TRACKED';
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden && communication.active && !communication.paused) {
    communication.pause();
    communication.state('paused', 'Capture paused while this tab is in the background. Resume when you’re ready.');
  }
});

async function recordPhrase(training = false) {
  if (busy || sending) return;
  if (communication.active) await endSession(false);
  const generation = ++attemptGeneration;
  setCaptureBusy(true);
  clearScan();
  let failed = false;
  try {
    if (!stream) {await startCamera();}
    if (!training && $('recognition-mode').value === 'avsr' && !config.avsr) throw new Error('Auto-AVSR is not configured. Use Teach phrases or Quick Phrases.');
    if (!training && $('recognition-mode').value === 'local' && new Set(recognizer.samples.map(s => s.phrase)).size < 2) {
      busy = false;
      setView('teach');
      busy = true;
      throw new Error('Teach at least two different phrases first. Start with three examples of each.');
    }
    const phrase = training ? $('teach-phrase').value : '';
    await countdown(training ? `Mouth: “${phrase}”` : 'Mouth your phrase once after the countdown.');
    $('capture-overlay').classList.remove('hidden');
    capturePhase('recording', training ? 'Learning your phrase' : 'Recording your words');
    if (!training && $('recognition-mode').value === 'avsr') {
      const blob = await captureVideo();
      await transcribeClip(blob, {}, generation);
    } else {
      const frames = await recognizer.capture($('camera'), captureProgress);
      if (training) {
        await recognizer.add(phrase, frames);
        $('teach-feedback').textContent = `Saved example ${recognizer.samples.filter(s => s.phrase === phrase).length} for “${phrase}”.`;
        renderTraining();
        toast('Example saved on this device.');
      } else {
        capturePhase('processing', 'Matching your phrase…');
        lastConfirmedFrames = frames;
        const ranked = recognizer.classify(frames);
        const response = await api('/api/choices', {source:'local-visual',candidates:ranked.map(r => r.phrase)});
        showDecision({...response,question:'These are the closest visual matches. Which did you mean?'});
      }
    }
  } catch (error) {
    if (error.name === 'AbortError' || generation !== attemptGeneration) return;
    failed = true;
    $('camera-hint').textContent = error.message || 'The recording could not be processed. Please try again.';
    throw error;
  } finally {
    if (generation !== attemptGeneration) return;
    clearInterval(processingTimer);
    processingTimer = null;
    setCaptureBusy(false);
    $('capture-overlay').classList.add('hidden');
    $('camera-badge').textContent = stream ? 'Camera active' : 'Camera off';
    if (!failed) $('camera-hint').textContent = 'Ready for another phrase. Keep the same lighting and camera position.';
    capturedBlob = null;
    startScanIfEnabled();
  }
}
$('record-button').addEventListener('click', guard(() => recordPhrase(false)));
$('teach-record').addEventListener('click', guard(() => recordPhrase(true)));
$('recognition-mode').addEventListener('change', renderTraining);
function renderTraining() {
  const counts = config.phrases.map(p => ({...p, count:recognizer.samples.filter(s => s.phrase === p.text).length}));
  $('training-list').innerHTML = counts.map(p => `<div class="training-row"><span>${escape(p.text)}</span><span class="sample-dots">${[0,1,2].map(i => `<i class="sample-dot ${p.count > i ? 'filled':''}"></i>`).join('')}</span><span class="sample-count">${p.count}/3</span></div>`).join('');
  $('teach-prompt').textContent = $('teach-phrase').value || 'I need water';
  const distinct = new Set(recognizer.samples.map(s => s.phrase)).size;
  $('model-note').textContent = $('recognition-mode').value === 'avsr'
    ? (config.avsr ? 'Pretrained visual model · runs on the server · accuracy unverified.' : 'Requires the Auto-AVSR environment and pretrained weights. See README.')
    : distinct >= 2 ? `${distinct} taught phrases · ${recognizer.samples.length} examples · experimental visual matching`
    : 'Teach at least two phrases to begin, or use the quick phrases below.';
  renderConnections();
}
$('teach-phrase').addEventListener('change', renderTraining);
$('teach-remove').addEventListener('click', guard(async () => {
  if (busy) return;
  const phrase = $('teach-phrase').value;
  if (!confirm(`Remove all recorded examples for “${phrase}”?`)) return;
  await recognizer.remove(phrase);
  renderTraining();
  $('validation-result').textContent = 'Training changed. Run the evaluation again.';
  toast('Examples removed.');
}));
$('validate-button').addEventListener('click', guard(async () => {
  const button = $('validate-button');
  button.disabled = true;
  $('validation-result').textContent = 'Evaluating each example against the other examples…';
  await new Promise(resolve => setTimeout(resolve,30));
  try {
    const result = crossValidate(recognizer.samples);
    $('validation-result').textContent = result ? `${result.correct} of ${result.total} held-out examples matched the correct phrase (${Math.round(result.correct / result.total * 100)}%). This is leave-one-out evaluation on your recordings, not a clinical accuracy estimate. Also test fresh clips without adding them to training.`
      : 'Record at least two examples each of two different phrases to evaluate.';
  } finally {button.disabled=false;}
}));

function scanTargets() {
  if (currentView === 'teach') return [$('teach-record')];
  if (currentView !== 'patient') return [];
  if (sent) return [$('new-button'),$('repeat-button'),$('help-button')];
  if (decision && choice !== null) return [$('confirm-button'),$('back-button'),$('edit-toggle')];
  if (decision) return [...$('candidates').querySelectorAll('button'),$('none-button')];
  return [$('session-toggle'), $('record-button'), ...$('quick-phrases').querySelectorAll('button'),$('help-button')];
}
function clearScan() {
  clearTimeout(scanTimer);
  scanTimer = null;
  document.querySelectorAll('.scan-focus').forEach(el => el.classList.remove('scan-focus'));
  scanIndex = -1;
}
function scanStep() {
  document.querySelectorAll('.scan-focus').forEach(el => el.classList.remove('scan-focus'));
  const targets = scanTargets().filter(el => !el.disabled && el.getClientRects().length);
  if (!targets.length || busy || sending || !$('scan-toggle').checked) return;
  scanIndex = (scanIndex + 1) % targets.length;
  targets[scanIndex].classList.add('scan-focus');
  targets[scanIndex].scrollIntoView({block:'nearest',behavior:'auto'});
  scanTimer = setTimeout(scanStep, scanInterval);
}
function startScan() {clearScan();scanStep();}
function startScanIfEnabled() {if($('scan-toggle').checked) startScan();}
$('scan-toggle').addEventListener('change', () => $('scan-toggle').checked ? startScan() : clearScan());
function hardwareSelect() {
  if (busy || sending) return;
  const target = document.querySelector('.scan-focus');
  if (target) target.click();
  else if (decision && choice !== null) $('confirm-button').click();
  else if (decision) selectChoice(0);
  else if (sent) resetInteraction();
  else $('record-button').click();
}
document.addEventListener('keydown', event => {
  if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
  const active = document.activeElement;
  const editing = ['TEXTAREA','SELECT'].includes(active.tagName) || (active.tagName === 'INPUT' && active.type !== 'checkbox');
  if (event.code === 'Space' && $('scan-toggle').checked && !editing) {event.preventDefault();hardwareSelect();return;}
  if (['INPUT','TEXTAREA','SELECT'].includes(active.tagName)) return;
  if (event.key.toLowerCase() === 'r' && currentView === 'patient') {event.preventDefault();guard(() => recordPhrase(false))();}
  if (event.key === 'Escape' && !busy && !sending) {if(choice !== null) $('back-button').click();else resetInteraction();}
});
$('scan-speed').addEventListener('input', () => {
  scanInterval = Number($('scan-speed').value);
  $('scan-speed-label').textContent = `${(scanInterval / 1000).toFixed(1)} seconds`;
  startScanIfEnabled();
});
$('usb-button').addEventListener('click', guard(async () => {
  if (bedside.connected) await bedside.disconnect(); else await bedside.connect();
}));
bedside.addEventListener('connected', () => {
  $('usb-button').innerHTML = `${icon('usb')}Disconnect controller`;
  toast('Controller connected. Close Arduino Serial Monitor if input is unavailable.');
  lastHardwareState = '';
  renderConnections();
});
bedside.addEventListener('disconnected', () => {
  $('usb-button').innerHTML = `${icon('usb')}Connect bedside controller`;
  renderConnections();
});
bedside.addEventListener('error', event => toast(`USB: ${event.detail}`,true));
bedside.addEventListener('command', guard(async event => {
  const [command, value] = event.detail.split('|');
  if (command === 'SELECT') hardwareSelect();
  if (command === 'NEXT') {if(!$('scan-toggle').checked) $('scan-toggle').checked=true;clearTimeout(scanTimer);scanStep();}
  if (command === 'BACK' && !sending) {if(choice !== null) $('back-button').click();else resetInteraction();}
  if (command === 'HELP') await requestHelp();
  if (command === 'SPEED') {
    const speed = Number(value);
    if (Number.isFinite(speed) && speed >= 800 && speed <= 6000) {
      scanInterval = speed;
      $('scan-speed').value = speed;
      $('scan-speed-label').textContent = `${(speed/1000).toFixed(1)} seconds`;
    }
  }
  if (command === 'READY') {lastHardwareState='';await syncHardware();}
}));
async function syncHardware() {
  if (!bedside.connected) return;
  const real = state.requests.filter(r => !r.simulated);
  const relevant = real.find(r => r.urgent && r.status === 'pending') || real.find(r => r.status === 'pending') || real[0];
  const status = relevant ? (relevant.urgent && relevant.status === 'pending' ? 'urgent' : relevant.status) : 'idle';
  const signature = `${status}|${relevant?.id || ''}`;
  if (signature !== lastHardwareState || Date.now() - lastHardwareSent > 5000) {
    await bedside.send(status, relevant?.text || 'Ready to listen');
    lastHardwareState = signature;
    lastHardwareSent = Date.now();
  }
}

function relativeTime(value) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  return seconds < 60 ? 'Just now' : seconds < 3600 ? `${Math.floor(seconds/60)} min ago` : new Date(value).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
}
function statCards(items) {
  return items.map(([label,number,note]) => `<div class="stat-card"><span>${escape(label)}</span><strong>${escape(number)}</strong><small>${escape(note)}</small></div>`).join('');
}
function renderCare() {
  const real = state.requests.filter(r => !r.simulated);
  $('care-summary').innerHTML = statCards([
    ['Waiting',real.filter(r=>r.status==='pending').length,'Confirmed requests'],
    ['Help requested',real.filter(r=>r.status==='pending'&&r.urgent).length,'Awaiting acknowledgment'],
    ['Acknowledged',real.filter(r=>r.status==='acknowledged').length,'Received by a caregiver'],
    ['Resolved',real.filter(r=>r.status==='resolved').length,'Marked complete']]);
  const rows = state.requests.filter(r => $('show-resolved').checked || r.status !== 'resolved');
  rows.sort((a,b) => (Number(b.urgent && b.status==='pending') - Number(a.urgent && a.status==='pending')) || b.created_at.localeCompare(a.created_at));
  $('care-requests').innerHTML = rows.length ? rows.map(r => `<article class="request-card ${r.urgent && !r.simulated ? 'urgent' : ''}"><div class="request-content"><span class="badge ${r.status === 'acknowledged' ? 'green':''}">${r.simulated ? 'SIMULATED DEMO' : escape(state.profile.room)} · ${escape(r.status)}</span><h3>${escape(r.text)}</h3><p>${escape(state.profile.name)} · ${escape(sourceNames[r.source] || r.source)} · ${escape(relativeTime(r.created_at))}${r.urgent ? ' · Help request' : ''}</p></div>${r.status !== 'resolved' ? `<button class="button ${r.status==='pending'?'primary':'secondary'}" data-request="${escape(r.id)}" data-status="${r.status==='pending'?'acknowledged':'resolved'}">${r.status==='pending'?'Acknowledge':'Mark resolved'}</button>`:''}</article>`).join('')
    : '<div class="empty-state">A quiet moment.<br>Confirmed requests will appear here when someone has something to say.</div>';
  $('care-requests').querySelectorAll('[data-request]').forEach(el => el.addEventListener('click', guard(async () => {
    el.disabled=true;
    try {await api('/api/request-status',{id:el.dataset.request,status:el.dataset.status});await poll();}
    finally {el.disabled=false;}
  })));
}
$('show-resolved').addEventListener('change', renderCare);
function renderInsights() {
  const metrics = state.metrics;
  $('insight-stats').innerHTML = statCards([
    ['Words made heard',metrics.confirmed || 0,'Confirmed requests · excludes demos'],
    ['Time to confirm',metrics.average_confirmation_seconds == null ? '—' : `${metrics.average_confirmation_seconds}s`,'After candidates are displayed'],
    ['Time to acknowledge',metrics.average_ack_seconds == null ? '—' : `${metrics.average_ack_seconds}s`,'For acknowledged requests'],
    ['Different interpretation',metrics.corrected || 0,'Confirmed text differs from raw input']]);
  const rows = state.requests.filter(r => !r.simulated), counts = {};
  rows.forEach(r => counts[r.source] = (counts[r.source] || 0) + 1);
  $('source-chart').innerHTML = Object.keys(counts).length ? Object.entries(counts).map(([source,count]) => `<div class="source-row"><div class="source-label"><span>${escape(sourceNames[source] || source)}</span><span>${count}</span></div><div class="source-track"><div class="source-fill" data-width="${count / rows.length * 100}"></div></div></div>`).join('') : '<p class="muted">Confirm a real request to begin measuring your session.</p>';
  document.querySelectorAll('[data-width]').forEach(el => el.style.width = `${el.dataset.width}%`);
  $('memory-list').innerHTML = state.memory.length ? state.memory.map(m => `<div class="memory-item">${escape(m.confirmed)}<small>From “${escape(m.raw)}” · confirmed ${m.uses} ${m.uses===1?'time':'times'}</small></div>`).join('') : '<p class="microcopy">Your confirmed words will appear here. Sample demo phrases are never added.</p>';
  $('history-body').innerHTML = rows.map(r => `<tr><td>${escape(r.text)}</td><td>${escape(sourceNames[r.source])}</td><td>${escape(r.status)}</td><td>${escape(new Date(r.created_at).toLocaleTimeString())}</td></tr>`).join('');
  const pipeline = state.pipeline || {}, evaluation = state.evaluation || {};
  const seconds = value => value == null ? '—' : `${(value/1000).toFixed(1)}s`;
  $('pipeline-stats').innerHTML = statCards([
    ['Visual attempts',pipeline.attempts || 0,'Actual model calls · not sample demos'],
    ['Time to suggestions',seconds(pipeline.average_ms),'Includes cold startup when applicable'],
    ['Visual processing',seconds(pipeline.inference_ms),'Average model + video processing'],
    ['Atlas pending sync',state.pending_sync || 0,'Stored locally until cloud write succeeds']]);
  $('evaluation-summary').innerHTML = `<h2>Measured, not assumed.</h2>${evaluation.clips ? `<div class="evaluation-comparison"><div><span>Raw model word error rate</span><strong>${Math.round(evaluation.raw_wer*100)}%</strong></div><span>→</span><div><span>Top suggestion word error rate</span><strong>${Math.round(evaluation.suggestion_wer*100)}%</strong></div></div><p class="microcopy">${evaluation.clips} evaluated attempts · ${evaluation.words} reference words. References were entered by the tester. Results describe these attempts only; they are not a patient accuracy estimate.</p>` : `<p class="muted">After a real model attempt, open “Evaluate this attempt” and enter the exact words you mouthed. This compares the raw transcript with the top suggestion using your reference text.</p>`}`;
}
$('export-button').addEventListener('click', guard(async () => {
  const data = await api('/api/export');
  const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)], {type:'application/json'}));
  const link = document.createElement('a');link.href=url;link.download=`unmute-session-${new Date().toISOString().slice(0,10)}.json`;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}));
$('profile-form').addEventListener('submit', guard(async event => {
  event.preventDefault();
  const profile = await api('/api/profile', {name:$('profile-name').value,room:$('profile-room').value,names:$('profile-names').value,context:$('profile-context').value,scan_ms:scanInterval});
  state.profile = profile;
  updateProfile(profile);
  toast('Preferences saved.');
}));
['large-text','high-contrast','auto-speak'].forEach(id => {
  const saved = localStorage.getItem(`unmute-${id}`);
  if (saved !== null) $(id).checked = saved === 'true';
  if (id !== 'auto-speak') document.body.classList.toggle(id,$(id).checked);
  $(id).addEventListener('change', () => {
    localStorage.setItem(`unmute-${id}`,String($(id).checked));
    if (id !== 'auto-speak') document.body.classList.toggle(id,$(id).checked);
  });
});
$('token-save').addEventListener('click', guard(async () => {
  sessionStorage.setItem('unmute-token',$('access-token').value.trim());
  $('access-token').value='';
  await initializeBackend();
  toast('Connected to server.');
}));
async function poll() {
  if (pollInFlight) return;
  pollInFlight = true;
  try {
    state = await api('/api/state');
    if (state.model_worker) config.model_worker = state.model_worker;
    if (state.atlas_status) config.atlas = state.atlas_status;
    backendOnline = true;
    $('connection').innerHTML='<i></i>Local server connected';
    $('offline-banner').classList.add('hidden');
    const pending = state.requests.filter(r=>!r.simulated&&r.status==='pending').length;
    $('pending-count').textContent=pending;
    $('pending-count').classList.toggle('hidden',!pending);
    updateSentStatus();
    if (currentView==='care') renderCare();
    if (currentView==='insights') renderInsights();
    if (currentView==='settings') renderConnections();
    await syncHardware();
  } catch {
    backendOnline = false;
    $('connection').textContent='Server disconnected';
    $('offline-banner').classList.remove('hidden');
  } finally {pollInFlight=false;}
}
async function initializeBackend() {
  config = await api('/api/config');
  $('teach-phrase').innerHTML=config.phrases.map(p=>`<option>${escape(p.text)}</option>`).join('');
  await poll();
  if (!backendOnline) throw new Error('Server is unavailable. Start python3 server.py.');
  updateProfile(state.profile);
  if (config.avsr && new Set(recognizer.samples.map(sample => sample.phrase)).size < 2) $('recognition-mode').value = 'avsr';
  renderPhrases();
  renderFavorites();
  renderTraining();
  renderConnections();
}
async function init() {
  try {await recognizer.open();} catch {toast('Browser storage unavailable. Quick phrases still work; training needs IndexedDB.',true);}
  try {await initializeBackend();} catch(error) {
    toast(error.message,true);
    if (error.message.includes('token')) setView('settings');
  }
  setView(location.hash.slice(1) || 'patient');
  setInterval(poll,2000);
}
init();
window.addEventListener('beforeunload', () => {communication.stop(); activeRecorder?.abort(); activeRequest?.abort(); stream?.getTracks().forEach(track => track.stop());});
