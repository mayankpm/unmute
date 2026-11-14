# Unmute

A patient-controlled silent communication prototype for HackUMass XIV.

**Record → review possible words → choose → confirm & speak → caregiver acknowledgment.**

The app includes a real webcam pipeline, experimental speaker-specific phrase
matching, an optional pretrained visual speech model, optional Gemini text
clarification, a caregiver queue, persistent local memory, session metrics, and
Arduino bedside controls. It is a hackathon research prototype, not a clinical
communication or emergency alert system.

## Run

```bash
cd /Users/mpolepalli/unmute
python3 server.py
```

Open **http://localhost:8080** in desktop Chrome or Edge. No Node, frontend build,
API key, or Python package installation is needed for the core app. Open the same
URL in another tab and choose **Care team** to acknowledge requests.

Python 3.11+ is recommended. The core was tested here with Python 3.15.2. Stop the
server with Ctrl+C. If port 8080 is busy, use `python3 server.py --port 8081`.

## What works without credentials

- Twelve selectable quick requests, each with explicit confirmation.
- Browser speech synthesis after confirmation; visible text remains if speech fails.
- Webcam capture with no microphone permission.
- **Teach phrases:** record labeled mouth-region examples; store descriptors in
  IndexedDB on the browser. Raw training video is not saved.
- **My trained phrases:** normalize grayscale mouth-region images and compare
  temporal sequences with dynamic time warping. This is actual visual matching,
  not a canned transcript. It is speaker/position dependent and unvalidated.
- One-switch scanning with adjustable timing, keyboard Space, and USB controls.
- A direct, deliberate **Request help** control independent of any AI inference.
- Patient review, rejection, repeat speech, and explicit caregiver acknowledgment.
- SQLite profiles, confirmed phrase memory, request state, and JSON export.
- Observed confirmation/acknowledgment times and source counts. Demo events are
  labeled and excluded from those metrics and from physical alarms.
- Local spelling suggestions and previously confirmed text interpretations.

The sample **Try demo** flow is explicitly simulated. It never pretends to read
your lips. Quick phrase buttons also do not use visual recognition.

## Teach your own visual phrases

1. In **My voice**, enable the camera. Use **Adjust guide** to frame your mouth.
2. Keep your head in the same position with good front lighting.
3. Open **Teach phrases**. Start with three visually distinct requests such as
   “I need water,” “Call my family,” and “Please adjust my pillow.”
4. Record three examples of each. Wait for the countdown, then mouth the phrase
   once during the three-second window. Use the same pace each time.
5. Run the leave-one-out evaluation. It excludes each query example from its own
   comparison set; it is not a clinical estimate or a substitute for fresh clips.
6. Return to **My voice**, select **My trained phrases**, and record a fresh clip.
   Review the closest matches; choose **None of these** if none is right.

The guide is manually positioned, not an automatic face tracker. Lighting and
movement outside the mouth region can affect the classifier. The fixed rejection
threshold is a heuristic, not calibrated confidence. No accuracy guarantee is
made. Do not describe this path as an open-vocabulary neural lip reader.

## Pretrained open-sentence lip reading

`scripts/setup_avsr.py` downloads the upstream visual-only research code and
weights into ignored directories and creates an isolated Python 3.11 environment.
It uses the inference repository associated with Auto-AVSR, including MediaPipe
face detection and upstream mouth cropping. On this machine the code, dependencies,
and approximately 894 MB weight archive were downloaded and configured in `.env`.

To install on another machine (macOS/Linux; adapt paths on Windows):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install uv
.venv/bin/python scripts/setup_avsr.py
```

The installer requires internet and several GB of disk space. It keeps downloads
under `vendor/`, weights under `models/`, and model packages under `.model-venv/`.
Google Drive may rate-limit the upstream weight link. It preserves existing
non-empty `.env` settings. Run `--activate-only` if downloads already exist.

Restart the server after installation, then select **Open sentences · Auto-AVSR**.
The browser records silent video; the server normalizes it to 25 fps with FFmpeg,
runs the visual model on CPU, and deletes temporary clips afterward. The adapter
uses beam size 10 and no external language model to reduce setup/CPU cost. It does
**not** reproduce the published benchmark configuration or accuracy.

```bash
python3 scripts/check_model.py
```

This runs an execution smoke test on the upstream sample GIF without audio and
writes `artifacts/model-smoke.json`. The test executed successfully here in 14.85
seconds for a three-second clip; a subsequent HTTP API test took 5.61 seconds.
Its transcript contained errors; this confirms
execution, not accurate recognition or new-speaker performance. On macOS the
MediaPipe tracker needs permission to initialize a graphics context even though
the speech model runs on CPU.

The optional model runs in a fresh subprocess for each clip; startup/model loading
adds latency. `AVSR_TIMEOUT` defaults to 120 seconds. The UI reports failures
instead of substituting sample sentences. The configured interpreter, repository,
and `.ini` file can also be set manually with `AVSR_PYTHON`, `AVSR_REPO`, and
`AVSR_CONFIG`. See `.env.example`.

## Gemini: clarification, not automatic speech

The server reads `.env` automatically. Add your own key locally:

```dotenv
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

Restart the server. Expand **Prefer to type?**, enter a transcript, check **Ask
Gemini**, and request interpretations. Gemini returns up to three possible
sentences and a clarification question in structured JSON. The patient chooses
and confirms; only then can a message be spoken or sent.

In **Preferences → Connections**, click **Test Gemini** to verify live generation
using synthetic text. The result shows the actual model, test suggestions, and
response time. The raw transcript is always retained among the options for real
requests, so the patient can choose it instead of an AI rewrite. A configured key
alone is labeled unverified; provider errors are displayed without exposing keys.

For the integrated pipeline, enable **Clarify open sentences with Gemini** before recording. You can also paste an Auto-AVSR transcript into the typed form. The text,
optional saved context/names, and up to ten confirmed examples go to Google only
when you enable this option. Camera video never goes to Gemini. API keys remain
server-side. Failed provider requests retain the raw input with a visible local
fallback. Choose a model available to your API account if the default is retired
or unavailable. Live structured generation has been verified with synthetic text using the configured Gemini model.

## Optional MongoDB Atlas integration

```bash
.venv/bin/python -m pip install -r requirements-optional.txt
```

Set `MONGODB_URI` in `.env`, optionally set `MONGODB_DATABASE`, and launch with
`.venv/bin/python server.py`. Configure Atlas database credentials and network
access for the laptop. SQLite remains the local source of truth; request events
are mirrored to Atlas as documents keyed by request ID, with status updates as
upserts. Existing recent requests are replayed on startup. The browser reports
the integration status. This optional cloud copy includes confirmed request text;
use synthetic hackathon data. An unavailable Atlas connection does not stop local
communication. A failed mirror attempt is retained in SQLite and replayed on
server restart; this is not a durable production replication system.

Use **Preferences → Connections → Test Atlas** after restarting the server. It
checks a database ping and reads the request collection count without inserting
test requests. A successful check confirms connectivity/read access; demonstrate
an actual confirmed request and acknowledgment to verify write access separately.

You may keep `MONGODB_URI` and optional `MONGODB_DATABASE` in a separate
`atlas-credentials.env` file instead. Unmute loads it automatically when those
settings are empty in `.env` or the shell; non-empty existing settings take
precedence. Other variables in that file are ignored. Both secret files are
excluded by `.gitignore`. Restart the server after changing credentials. Atlas
SRV connections use the system CA store where available; TLS verification stays
enabled.

## Hardware

See **[firmware/README.md](firmware/README.md)** for a complete pin table, LCD
contrast options, upload steps, protocol, and optional ESP32 pager.

- UNO: select, back, help; scan-speed knob; LEDs; passive buzzer; LCD1602.
- USB uses Web Serial at 115200 baud in desktop Chrome/Edge on localhost.
- Firmware compiles for Arduino Uno; physical wiring/USB behavior must be checked
  with the actual kit. No firmware was uploaded automatically.
- Optional pager requires identifying your actual Espressif board and configuring
  compatible GPIOs. `pager.ino` is supplied separately; do not assume the pictured
  packaging proves a specific ESP32 variant or pinout.

To reproduce the UNO compile without touching a device:

```bash
python3 scripts/check_firmware.py
```

This downloads tools into `vendor/arduino/` and writes compiled output under
`artifacts/uno-build/`.

## Network caregiver dashboard / optional pager

Localhost-only mode needs no token. To expose the prototype on a trusted private
hotspot, add a long `UNMUTE_TOKEN` to `.env` and run:

```bash
python3 server.py --host 0.0.0.0
```

On the caregiver device, open `http://LAPTOP-LAN-IP:8080/#care`, visit Preferences,
and enter the token. It stays in sessionStorage for that tab. Each API request
uses an Authorization header. Local browser cross-origin requests are rejected.
This is shared-token demo access, not multi-user authentication. It uses plain
HTTP on your hotspot; do not expose it on the public internet. Use localhost on
the patient laptop for camera and USB permissions. Hospital networking, clinical
authentication, and nurse-call integration are outside this prototype.

## Verification

```bash
python3 -m unittest discover -s tests -v
.venv/bin/python -m pip install playwright
.venv/bin/python scripts/browser_smoke.py
```

The browser script uses installed Google Chrome, an isolated temporary database,
and a synthetic webcam. It covers patient/caregiver synchronization, confirmation,
demo exclusion, text correction, profile and training persistence, webcam capture
without audio, keyboard scanning, direct help, XSS escaping, mobile overflow, simulated USB protocol, HTTP origin/auth behavior, and
ten deterministic recognizer checks. Screenshots go under `artifacts/`.

The app stores local request/profile data in `data/unmute.db`. Training examples
are browser-specific and do not automatically transfer to other browsers or
devices. **Session insights** exports request/profile data, not visual templates.
No background microphone capture, automatic clinical inference, or automatic
speech before confirmation is implemented.

## Files

| Path | Purpose |
| --- | --- |
| `server.py` | HTTP API, SQLite, confirmation state, Gemini, optional Atlas |
| `web/` | Responsive interface, camera, visual templates, speech, Web Serial |
| `adapters/auto_avsr.py` | Video normalization and upstream inference adapter |
| `firmware/` | UNO controller, optional ESP32 pager, wiring guide |
| `scripts/` | Optional model/tool downloads and verification |
| `tests/` | Backend behavior tests |
| `docs/DEMO.md` | Demo sequence and prize submission positioning |
| `source` | Your original handoff, preserved |

## Attribution and external code

The application code in `server.py`, `web/`, `adapters/`, and `firmware/` was written
for this prototype. Disclose AI-assisted development in your submission where
requested. The original handoff's benchmarking/competitor claims have not been
incorporated as product guarantees.

- [Visual Speech Recognition for Multiple Languages / Auto-AVSR inference](https://github.com/mpc001/Visual_Speech_Recognition_for_Multiple_Languages):
  Pingchuan Ma and collaborators. Downloaded code retains its license and notices;
  revision recorded at `vendor/avsr-provenance.json`. Its LICENSE includes research
  restrictions. Review those and model/dataset terms before any commercial use.
- [Auto-AVSR paper](https://arxiv.org/abs/2303.14307).
- [Google Gemini API](https://ai.google.dev/api/generate-content): optional structured
  text suggestions, called using REST; no client API key.
- [Web Serial API](https://developer.chrome.com/docs/capabilities/serial).
- [PyMongo](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/get-started/):
  optional Atlas mirror.
- Arduino LiquidCrystal, optional ESP32 Arduino core, and ArduinoJson retain their
  respective upstream licenses. Browser speech synthesis is provided by the OS.
