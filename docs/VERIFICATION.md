# Verification performed November 14, 2026

| Check | Result |
| --- | --- |
| Backend behavior | 16 unittest cases passed |
| Browser integration | Passed in installed Google Chrome via Playwright |
| Visual recognizer algorithm | 10 deterministic browser checks passed |
| Camera capture | Passed with browser-provided synthetic video; no audio tracks |
| Template persistence | Recorded example survives browser reload |
| Patient / caregiver | Confirm → receive → acknowledge → resolve synchronizes across tabs |
| One-switch input | Keyboard selection/confirmation passed |
| USB protocol | Browser stream mock passes input/output checks; no physical board attached |
| HTTP origin/auth | Cross-origin mutations, unconfirmed requests, and missing network token rejected |
| Mobile layout | Checked at 390px; no document or camera-region horizontal overflow |
| Text escaping | User-supplied HTML remains text |
| UNO firmware | Compiled for arduino:avr:uno; 5,548 bytes flash, 660 bytes global RAM |
| Pretrained visual model | Successfully executed on the upstream sample, without audio |
| Video upload API | `/api/transcribe` successfully invokes the actual model |

The three-second sample produced `IN ANY CASE ONE CITIZEN COACH AGREE`, which
contains recognition errors. The first successful adapter smoke test took 14.85
seconds, and the subsequent HTTP API test took 5.61 seconds. These timings include
model startup and decoding and are observations on this laptop, not performance
guarantees. This was not a held-out patient/new-speaker accuracy evaluation.

CPU speech inference uses beam size 10 and no external language model. The
MediaPipe tracker needs a macOS graphics context; it failed inside the restricted
tool sandbox and succeeded when run with the required host permissions.

Live Gemini structured generation was subsequently verified with synthetic text
using gemini-3.1-flash-lite (about 0.9 seconds). Live Atlas connectivity, request
write/read, and acknowledgment updates were also verified using a synthetic demo
request. The cloud test document was removed afterward; the safe result is saved
in artifacts/atlas-smoke.json. Separate atlas-credentials.env fallback loading and
existing-configuration precedence were checked. Speech synthesis is implemented but automated tests disabled audible
playback. Physical wiring, button behavior, LCD contrast, and ESP32 pager behavior
remain unverified on hardware. The ESP32 variant was not identifiable from its
packaging photo, so that optional sketch is not claimed as board-verified.

Reproduction instructions are in `README.md`. Screenshots, model output, a silent
test clip, and compiled UNO files are in the ignored `artifacts/` directory.
