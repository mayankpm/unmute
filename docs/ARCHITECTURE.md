# Architecture

```mermaid
flowchart TD
    Camera[Silent webcam · no audio] --> Tracker[Browser worker: local face landmarks]
    Tracker --> Gate[Mouth-motion segmentation · bounded buffer + pre-roll]
    Gate --> Clip[Temporary silent video clip]
    Manual[Manual three-second capture] --> Clip
    Clip --> AVSR[Persistent Auto-AVSR worker · CPU]
    AVSR --> Hypotheses[Raw transcript + actual decoder alternatives]
    Hypotheses --> Review[Patient review · word correction · rejection]
    Hypotheses -->|Explicit opt-in: text only| Gemini[Gemini + optional context and confirmed examples]
    Gemini --> Review
    Quick[Quick phrases + personal shortcuts] --> Review
    Review -->|Explicit confirmation| Voice[Browser speech synthesis]
    Review -->|Explicit confirmation| Local[SQLite request + versioned outbox]
    Local -->|Retry upsert| Atlas[MongoDB Atlas]
    Local --> Care[Caregiver queue]
    Care -->|Explicit acknowledgment| Local
    Local --> Bedside[Patient status + optional UNO over USB]
    Review -->|Tester enters reference words| Evaluation[Raw/top-suggestion error measurements]
```

The gate detects movement, not meaning. It does not stream words or determine a
patient's intent. One phrase is processed at a time, capture pauses for review,
and the patient has to confirm before speech or request creation. Background tabs
pause automatic capture. Stop/cancel invalidates stale client results; model
cancellation terminates its process group so retries do not wait on orphan jobs.

The model owner is `model_worker.py`. The web server remains independent of
PyTorch and communicates with a Python 3.11 subprocess using bounded JSON lines.
The worker loads weights once, normalizes temporary clips to 25 fps, tracks/crops
the face with upstream code, and obtains actual beam-search hypotheses.

SQLite migrations use CREATE TABLE IF NOT EXISTS, retaining existing local data.
The cloud outbox stores the latest version of each request. A successful write
only removes the matching version: a newer acknowledgment cannot be accidentally
cleared by an older in-flight sync. Cloud failures never imply acknowledgment.

The only routine cloud payload to Gemini is text explicitly enabled by the user.
Atlas mirrors confirmed request text/status. Model weights, runtime assets,
credentials, local databases, and recordings are excluded from the Git repository.
No patient training dataset or production clinical accuracy is claimed.
