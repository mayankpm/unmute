# Unmute

**A little movement. A whole voice.**

Unmute is a patient-controlled silent communication prototype for HackUMass XIV.
Start a communication session, mouth a phrase, review the possible words, correct
anything that is wrong, and confirm before the message is spoken or sent.
A caregiver can acknowledge the request, and the patient sees that response.

## Run on this laptop

```bash
cd /Users/mpolepalli/unmute
.venv/bin/python server.py
```

Open **http://localhost:8080** in desktop Chrome or Edge. The server preloads the
visual model in the background. Open a second tab at **http://localhost:8080/#care**
for the caregiver queue. Stop the server with Ctrl+C.

The Python web server uses only the standard library. PyMongo is optional for
Atlas. Neural inference has its own Python environment; browser face tracking
uses downloaded local WebAssembly assets. No Node.js build step is required.

## The MVP experience

1. Click **Start communicating** and permit camera access. No microphone is used.
2. Wait until the session says **Ready for your words**. Keep your whole face
   visible with good front lighting.
3. Mouth a short phrase naturally, then pause. Mouth landmarks trigger capture
   automatically and a quiet interval ends the phrase. A short pre-roll reduces
   loss of the first mouth movement. Phrases are bounded to a few seconds.
4. Capture pauses while you review the suggestions. Nothing is spoken or sent.
5. Select a candidate. If necessary, choose **Correct a word or sentence**, select
   a word, apply its replacement, and review the corrected sentence.
6. Click **Confirm & speak**, or use one-switch scanning and the physical Select
   button. The confirmed message appears in the caregiver queue.
7. A caregiver explicitly acknowledges or resolves it. The patient's status and
   connected bedside device update to reflect that action.
8. Choose **Say something else** to resume capture, or **End session** to stop the
   session and release the camera.

**Record a phrase** remains available for a manual three-second attempt. Quick
phrase buttons work without a camera or any model. **Request help** is a direct,
intentional control independent of AI interpretation.

This is a hackathon research prototype, not a clinical communication system or
medical alarm. Mouth motion detection is heuristic segmentation, not proof that
someone is speaking; chewing and other movement can trigger it. Patient review
and rejection are integral to the experience.

## What makes this more than a model demo

- **Continuous communication session:** local face landmarks track mouth motion
  on a worker thread, with clear ready/capturing/processing/review states.
- **Persistent visual model:** the server keeps one Auto-AVSR worker loaded rather
  than launching and loading weights for every phrase. Cancellations/timeouts stop
  that process group and allow a fresh attempt; a canceled model must reload.
- **Real visual alternatives:** up to three distinct hypotheses come from the
  neural decoder. They are not displayed as calibrated confidence probabilities.
- **Gemini clarification:** optional text interpretation uses those visual
  alternatives, saved context/names, and confirmed examples. The raw transcript
  always remains available. No camera video goes to Gemini.
- **Patient-controlled correction:** editing creates a fresh review decision.
  Speech and request creation still require explicit confirmation.
- **Personal phrase bank:** save up to 12 personal shortcuts. This saves words,
  not a cloned voice or neural model fine-tune.
- **Caregiver acknowledgment:** a visible request-to-receipt loop, with optional
  Arduino display, LEDs, buzzer, and physical selection controls.
- **Local-first persistence:** SQLite stores confirmed requests and an Atlas
  outbox. Failed cloud writes retry from durable local records. Versioned outbox
  entries prevent an older sync from clearing a newer acknowledgment update.
- **Evidence:** timing measurements and tester-entered reference text support
  raw-versus-top-suggestion word error measurements. No accuracy is invented.

## Models and installation on another machine

These setup helpers target macOS/Linux. The downloaded packages, runtimes, and
weights are intentionally excluded from Git; setup scripts recreate them.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install uv -r requirements-optional.txt
.venv/bin/python scripts/setup_avsr.py
.venv/bin/python scripts/setup_vision.py
.venv/bin/python server.py
```

The first helper downloads an isolated Python 3.11 runtime, inference packages,
upstream research code, and approximately 894 MB of visual speech model weights.
It configures `AVSR_PYTHON`, `AVSR_REPO`, and `AVSR_CONFIG` in `.env` without
replacing non-empty existing settings. Allow several GB of disk space. Google
Drive may impose download quotas. `--activate-only` uses existing model downloads.

The second helper downloads about 22 MB of local browser face-tracking assets,
including MediaPipe Tasks Vision 0.10.21 and the Face Landmarker task model.
Hashes and source URLs are stored in `web/assets/vision/manifest.json`.

**Visual speech:** the Auto-AVSR-associated multilingual inference repository,
`LRS3_V_WER19.1` checkpoint; CPU, beam size 10, no external language model.
This does not reproduce the checkpoint's published benchmark configuration or
word error rate. The worker uses upstream detection, cropping, encoder, and beam
search; it returns actual decoder alternatives. `AVSR_THREADS` defaults to 4 and
`AVSR_TIMEOUT` defaults to 120 seconds.

**Mouth tracking:** browser-local MediaPipe Face Landmarker. Image frames are
transferred to a local browser worker; only geometry is returned to the UI. Face
tracking and neural lip reading are separate tasks.

A persistent-worker execution benchmark on this laptop's three-second upstream
sample observed 29.6 seconds for its first cold run and about 1.8 seconds for each
of two warm runs. Subsequent cold loading was faster after caches warmed. These
are execution measurements on one sample, not accuracy or latency guarantees.

An optional upstream English decoding language model can be prepared with
`scripts/setup_language_model.py`. It writes `models/unmute-visual-lm.ini` without
changing `.env`. Compare it with `scripts/benchmark_worker.py --config
models/unmute-visual-lm.ini --report artifacts/worker-benchmark-lm.json` before
choosing it. The default remains the visual decoder: one sample did not establish
an accuracy gain from that external language model.

## Gemini setup

Add your key to `.env`:

```dotenv
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

Restart the server and use **Preferences → Connections → Test Gemini**. A
configured key is distinguished from a successful live generation test. Errors
are sanitized; API keys are never returned to the browser.

Enable **Clarify open sentences with Gemini** to opt in for actual capture. The
server passes the raw transcript, visual hypotheses, optional saved context and
names, and recent confirmed examples to Gemini for structured suggestions and a
clarification question. The original transcript remains one of the choices.
Provider failures return the original visual suggestions with a visible warning.

The typed form also supports Gemini; it is useful for testing correction but is
not counted as a visual recognition evaluation. Use a model available to your
account if the configured model is retired. The API is optional; local visual
recognition and quick phrases do not need internet after model installation.

## MongoDB Atlas setup

Put these settings in `.env` or `atlas-credentials.env`:

```dotenv
MONGODB_URI=mongodb+srv://username:password@your-cluster.example/
MONGODB_DATABASE=unmute
```

The separate Atlas file fills empty MongoDB settings; non-empty shell or `.env`
settings take precedence. Other variables in that file are ignored. Both secret
files are excluded by `.gitignore`. Install `requirements-optional.txt`, give the
Atlas database user read/write access, and allow the laptop's IP in Atlas Network
Access. The verified system CA store is used for SRV connections where available;
TLS verification remains enabled.

Restart and select **Preferences → Connections → Test Atlas**. This checks a ping
and request collection read without writing a test request. To verify writes,
confirm a synthetic request and acknowledge it in the caregiver view, then inspect
its Atlas document. The `requests` collection uses the request ID as `_id`.

SQLite is the source of truth. A versioned `mirror_outbox` table retains pending
cloud writes and the mirror retries while the server is running. Session insights
shows pending sync count. Requests continue locally during cloud outages. This is
single-laptop demo replication, not a production clinical data architecture.

## Measure instead of guessing

After a real visual attempt, open **Evaluate this attempt · demo lab** and enter
exactly what you intended to mouth. The app compares that reference with the raw
transcript and top suggestion using word-level edit distance. Re-evaluating one
attempt replaces its previous result. Simulated demos, manually edited sentences,
and typed Gemini correction tests are excluded from visual error measurements.

Session insights shows sample size, reference word count, weighted raw/top-suggestion
WER, model call counts, observed latency, and pending cloud sync. WER can exceed
100% when extra words are inserted. The report describes those attempts, not
clinical accuracy, unseen speakers, or general population performance.

The sample **Try demo** flow is explicitly simulated and never claims to read lips.
Demo requests are excluded from real-session metrics and physical alarms.

## Personal phrase training

**Teach phrases** retains a separate offline experimental template matcher.
Record three examples of at least two visually distinct phrases using a stable
manual mouth guide, camera position, and lighting. Normalized mouth-region image
sequences are compared using dynamic time warping. Run leave-one-out evaluation,
then test fresh clips without adding them to training. Cropped descriptors live
in this browser's IndexedDB; raw training videos are not stored.

This is not neural fine-tuning. It is speaker/position dependent and unvalidated.
The main automatic session uses the pretrained visual model, not this matcher.
A useful future fine-tune would require consented, labeled examples and a separate
held-out set; no such patient dataset is included or claimed here.

## Hardware

See **[firmware/README.md](firmware/README.md)** for pin tables, contrast options,
upload instructions, the USB protocol, and optional ESP32 pager setup.

The UNO sketch supports Select, Back, Help, a scan-speed knob, LEDs, passive
buzzer, and LCD1602. Web Serial runs at 115200 baud in desktop Chrome/Edge on
localhost. The sketch compiles for Arduino Uno. Physical wiring, LCD contrast,
and device behavior still need checking with the actual kit. The Espressif
packaging did not identify the board variant; choose suitable pins before using
the optional pager sketch. Nothing connects to hospital equipment.

```bash
python3 scripts/check_firmware.py
```

## Local network demo

To use a caregiver device or optional pager on a trusted private hotspot, set a
long `UNMUTE_TOKEN` in `.env`, then run:

```bash
.venv/bin/python server.py --host 0.0.0.0
```

Open `http://LAPTOP-LAN-IP:8080/#care` on the caregiver device and enter the token
in Preferences. Keep the patient camera/USB view at `http://localhost:8080`.
The token uses an Authorization header and stays in the browser tab's
sessionStorage. The hotspot endpoint uses HTTP, not encrypted transport. Do not
expose this single-profile shared-token demo on the public internet.

## Verification

```bash
python3 -m unittest discover -s tests -v
.venv/bin/python -m pip install playwright
.venv/bin/python scripts/browser_smoke.py
.venv/bin/python scripts/recording_smoke.py
.venv/bin/python scripts/mvp_smoke.py
.venv/bin/python scripts/vision_smoke.py
.venv/bin/python scripts/benchmark_worker.py
```

Browser workflow tests use Chrome, a synthetic webcam, controlled model/geometry
fixtures where stated, and temporary databases. The vision smoke test uses the
actual local landmark model on the upstream silent sample. The worker benchmark
uses the actual neural speech model. Neither proves recognition on a new speaker.

`live_mvp_check.py` additionally exercises real Gemini generation and Atlas
writes/acknowledgments using upstream/synthetic data, then removes its cloud test
document. This is optional and requires your own credentials. Safe reports and
screenshots go under ignored `artifacts/`.

Data is in `data/unmute.db`; browser templates and preferences are browser-specific.
Exporting a session includes textual request/profile/evaluation data, not videos
or browser templates. Temporary inference clips are deleted when processing ends.
API keys stay server-side. Optional Atlas replication sends confirmed request text;
use synthetic hackathon data.

## Code map and attribution

| Path | Purpose |
| --- | --- |
| `server.py` | HTTP API, SQLite, Gemini, Atlas outbox, review/evaluation |
| `model_worker.py` | Persistent process, warmup, cancellation, timeout recovery |
| `adapters/avsr_worker.py` | Local neural video inference and real decoder hypotheses |
| `web/` | Patient/caregiver UI, session state, tracking, capture, controls |
| `firmware/` | UNO controller, optional pager, wiring guide |
| `scripts/`, `tests/` | Reproducible setup and verification |
| `docs/DEMO.md` | Judging demo and submission positioning |
| `source` | Original team handoff |

The app was developed with AI assistance. Disclose external and AI-assisted work
as required by the event. The original handoff's competitor/accuracy claims are
not product guarantees.

- [Visual Speech Recognition for Multiple Languages](https://github.com/mpc001/Visual_Speech_Recognition_for_Multiple_Languages)
  and [Auto-AVSR](https://arxiv.org/abs/2303.14307), Pingchuan Ma and collaborators.
  Downloaded code retains upstream notices. Its license includes research
  restrictions; review model/dataset terms before commercial use. The downloaded
  revision is in `vendor/avsr-provenance.json`.
- [MediaPipe Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker):
  pretrained face geometry; retain upstream Apache 2.0/software/model notices.
- [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
  and [PyMongo](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/):
  optional live cloud services, configured with your own credentials.
- Arduino LiquidCrystal, optional ESP32 Arduino core, and ArduinoJson retain their
  upstream licenses. Speech synthesis is provided by the browser/OS.
