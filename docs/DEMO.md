# Demo and submission

## A coherent two-minute story

“Having something to say should not depend on being able to make a sound.
Unmute lets a person review and confirm their mouthed request, speak it aloud,
and see when a caregiver acknowledges it.”

1. Open My voice and Care team in two browser tabs/windows.
2. Explain the difference between the actual visual model, taught visual phrase
   matching, quick buttons, and the explicitly simulated demo. Choose a mode you
   have tested on the actual speaker.
3. Mouth a taught phrase or use the pretrained visual model. Show the candidates.
4. Select with the UNO button (or keyboard scanning). Pause on the separate
   confirmation step: the patient has the last word.
5. Confirm. The message is spoken; the caregiver queue receives it. If connected,
   the physical display/LEDs show the pending request.
6. Acknowledge it in Care team. Show the patient's screen and hardware update.
7. Show a noisy typed transcript (“call my dotter”). With your own Gemini key,
   explicitly opt in to structured clarification. Reject incorrect suggestions
   when needed. Never present plausible generation as recovered ground truth.
8. Show observed timing and the visual model's actual held-out evaluation, if
   you ran one. State the sample size and test conditions.

If recognition is unreliable, demonstrate the accessible confirmation/quick
phrase path honestly and show a labeled recorded example of successful visual
inference. The included sample demo tests interaction, not lip-reading accuracy.

## Prize focus

Our recommendation is **Best Accessibility Hack**, plus relevant sponsor opt-ins.
Public Devpost requirements allow one `[HACKUMASS]` category, automatic grand-prize
consideration, and additional sponsor selections. Recheck organizer announcements.

- Accessibility: one-switch access, adjustable speed, direct help, large text,
  explicit patient control, and caregiver acknowledgment.
- Gemini: structured interpretation/clarification using optional context and
  confirmed examples. Must demonstrate actual API use with your own key.
- MongoDB Atlas: actual request documents and acknowledgment updates. Show live
  Atlas records; a local SQLite log alone is not Atlas usage.
- Grand prize: a coherent, working end-to-end interaction and honest measurements.

Do not claim a sponsor integration was used unless you actually configured it.
Use Preferences → Connections → Test Gemini / Test Atlas before judging. Gemini
tests send synthetic text; Atlas tests only ping/read the request count. A passing
Atlas check does not prove write permissions: confirm and acknowledge a real
demo-session request, then inspect its document in Atlas.
Do not claim personal model fine-tuning: local templates and text memory are the
implemented personalization mechanisms. Do not claim offline Gemini: only the
local visual and quick-button paths work without internet.

## Submission material

- Public repository, including original code and all external-code attributions.
- Clear architecture: browser camera/controls → local inference or templates →
  patient confirmation → speech + persistent request → caregiver acknowledgment.
- Your original contribution versus the pretrained upstream model.
- A short demo video under three minutes, as recommended by the rules.
- Your actual sample size, fresh-clip accuracy, and latency if measured. Automated
  browser/synthetic tests prove functionality, not lip-reading performance.
- Actual API/database/hardware use, including visible setup limits.

Public references checked November 14, 2026:
[Devpost requirements and prizes](https://hackumass-xiv.devpost.com/),
[rules](https://hackumass-xiv.devpost.com/rules),
[main event site](https://www.hackumass.com/).

Rules say initial submission Saturday before 11:59 PM EST and edits until Sunday
10 AM; the main event site showed 9 AM as the final deadline. Work to the earlier
deadline unless organizers clarify it.
