# HackUMass demo

## Before judging

- Start `.venv/bin/python server.py` early so the visual model is warm.
- Use front lighting and a stable webcam with one whole face in view.
- Test the actual speaker and a few short phrases; do not rely on benchmark WER.
- In Preferences, verify Gemini and Atlas. Enable Gemini's text-only option if
  demonstrating it. Prepare synthetic requests, not real patient information.
- Check the physical controller if using it. Keep manual capture and quick phrases
  available, and record a backup video of a genuine successful interaction.
- Open the caregiver view in a second window. Capture pauses for patient review;
  switching a still-armed capture tab into the background also pauses it.

## Two-minute demonstration

**Opening:** “Having something to say shouldn't depend on being able to make a
sound. Unmute helps a person turn mouthed words into a confirmed request—and
shows them when someone has acknowledged it.”

1. Start a communication session. Show that quiet frames do not generate requests.
2. Mouth a short phrase and pause. The app detects movement and captures the phrase
   without pressing Record for each attempt.
3. Show the visual hypotheses and optional Gemini clarification. Point out the raw
   transcript, and reject incorrect suggestions rather than treating plausible
   text as recovered speech.
4. Select a suggestion. If necessary, correct a word and review it again.
5. Confirm using the screen or one-switch controller. The message is spoken and
   appears on the caregiver queue. The bedside device shows the request state.
6. Acknowledge it on the caregiver screen. Show the patient's status change.
7. Save a personal request, such as a family member's name, as a shortcut.
8. Show observed warm latency and the actual reference-based error report, including
   the number of attempts and reference words. Show the Atlas document update.

## Contribution and prize positioning

Recommend one primary category: **Best Accessibility Hack**. Sponsor opt-ins can
include **Gemini API** and **MongoDB Atlas** when actually used. Recheck the event's
current submission rules; public Devpost requirements previously allowed one
`[HACKUMASS]` category plus sponsor opt-ins and automatic grand-prize consideration.

Your implementation is the communication system around the research model:
local automatic capture, persistent inference, patient review and repair, personal
shortcuts, accessible selection, caregiver acknowledgment, recoverable cloud sync,
and measurements. Attribute Auto-AVSR and MediaPipe explicitly.

Be precise about what was built:

- This is automatic phrase segmentation, not continuous word-by-word streaming.
- Gemini receives text, not the camera stream, and must not be credited with
  accurately reading lips. Its suggestions require patient confirmation.
- Quick buttons and the sample demo are not visual recognition.
- Personal templates/shortcuts are not neural fine-tuning or voice cloning.
- Warm latency on one upstream sample is not a new-speaker accuracy result.
- The physical prototype sends demo requests; it is not a hospital nurse-call system.

## Submission checklist

Public code, external-code attribution, a short demo video, setup steps, architecture,
actual sponsor use, and test conditions/sample sizes. Describe limitations plainly.
The live functionality and coherent patient-to-caregiver interaction are the story.

References checked November 14, 2026:
[Devpost](https://hackumass-xiv.devpost.com/),
[rules](https://hackumass-xiv.devpost.com/rules),
[event site](https://www.hackumass.com/).

Public deadline information conflicted between 9 AM and 10 AM Sunday EST. Work to
the earlier time unless organizers clarify it. Initial submission was required
before Saturday 11:59 PM EST.
