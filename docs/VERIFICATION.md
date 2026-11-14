# MVP verification — November 14, 2026

| Check | Result |
| --- | --- |
| Backend behavior | 36 unittest cases passed |
| Core browser flow | Patient/caregiver synchronization, confirmation, demo exclusion, text correction, persistence, one-switch input, help, simulated USB, origin/auth checks, escaping, and mobile layout passed |
| Visual template algorithm | 10 deterministic browser checks passed |
| Recording recovery | Real synthetic-webcam capture, elapsed processing state, cancellation before upload, delayed responses, model error, and missing recorder-stop watchdog passed |
| MVP browser flow | Silence gating, automatic segmentation, pause for review, word repair, evaluation, personal shortcuts, camera release, and responsive layout passed with controlled geometry/model fixtures |
| Actual browser face model | Local MediaPipe WebAssembly produced mouth geometry on the upstream silent sample |
| Actual speech worker | Neural inference completed; the same process handled repeated clips |
| Worker recovery | Cancellation and timeout kill the process group and allow the next request |
| Evaluation integrity | Demo/manual edits/typed correction tests excluded from visual WER; repeat evaluation replaces the previous one |
| Durable Atlas outbox | Restart persistence and acknowledgment-version race checks passed |
| Live Gemini + Atlas | Actual generation, request write/read, acknowledgment update, and drained outbox verified using synthetic/upstream data; cloud test document removed |
| Full actual automatic session | Chrome used upstream video as a fake webcam; actual face tracking, automatic capture, neural inference, and live Gemini reached the review screen without a manual recording click |
| UNO firmware | Earlier compile passed for arduino:avr:uno; 5,548 bytes flash, 660 bytes global RAM |

## Measured execution

The baseline persistent-worker benchmark used the same three-second silent
upstream sample for all runs:

- First cold run: **29,557 ms**.
- Warm runs: **1,776 ms** and **1,806 ms**.
- A later isolated worker startup measured **4,468 ms**, after caches had warmed.
- Full actual automatic-session test: **17.17 seconds** from starting the session
  to review, including preparation and automatic capture. The resulting clip's
  processing was **5.5 seconds**: **4.7 seconds** visual inference and **0.8 seconds**
  Gemini. That test used a looping prerecorded face, not a live patient/new speaker.

These are observations on this laptop and sample, not performance guarantees.
The transcript contained substantial errors. The tests prove execution and
patient-controlled flow, not clinical accuracy or reliable recognition on a new
speaker. No personal neural fine-tuning or patient training dataset is claimed.

An optional upstream English decoding language model was also benchmarked. It
changed the transcript and added latency (warm runs about 2.3 seconds), but this
single sample did not establish an accuracy gain, so the default remains the
visual decoder without that external language model. The optional setup helper
and alternate `.ini` are available for a properly labeled evaluation.

## Limits

Automated browser fixtures prove UI/state behavior; they do not establish visual
recognition accuracy. The actual landmark and full automatic-session tests are
separate from those controlled fixtures. Speech synthesis is implemented, while
routine browser tests disable audible playback. Physical wiring, button behavior,
LCD contrast, and ESP32 pager operation remain unverified on the kit. Its exact
Espressif variant was not identifiable from the packaging photo.

Safe reports, screenshots, a silent upstream test clip, and compiled UNO output
are in ignored `artifacts/`. Credentials and patient/local data are excluded from
Git. Reproduction commands are in `README.md`.
