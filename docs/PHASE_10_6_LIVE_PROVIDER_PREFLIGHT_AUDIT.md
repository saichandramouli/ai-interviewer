# Phase 10.6 — Live Provider Integration Preflight Audit Report

**Date:** 2026-11-03  
**Status:** COMPLETE  
**Overall Verdict:** **READY WITH WARNINGS** (Ready for live testing pending provision of Deepgram and ElevenLabs API credentials in `.env`)

---

## 1. Executive Summary

This preflight audit evaluates the readiness of the Standalone AI Interviewer application to transition from mock providers to live third-party AI and voice APIs:
- **NVIDIA Nemotron** (`nvidia/nemotron-3.5-lightning-30b-a3b`) via NVIDIA NIM REST API for dynamic interview dialogue orchestration and post-interview rubric evaluation.
- **Deepgram STT** (`nova-3`, language: `en-IN` / `en-US`) for high-fidelity speech-to-text transcription of candidate audio turns.
- **ElevenLabs TTS** (`eleven_multilingual_v2`, default voice: `21m00Tcm4TlvDq8ikWAM` Rachel) for text-to-speech synthesis of interviewer responses.
- **OpenAI** (`gpt-4o-mini`) utilized specifically for initial structured interview plan generation.

The codebase already features a fully realized factory pattern (`SpeechProviderFactory`), clean abstraction layers (`BaseSTTProvider`, `BaseTTSProvider`), explicit request timeouts, sanitization against prompt injection, structured JSON response extraction, and browser-native audio format support (`audio/webm;codecs=opus`).

The system is structurally ready for live execution once API keys for Deepgram and ElevenLabs are provided in `backend/.env`.

---

## 2. Current Provider Configuration

### 2.1 NVIDIA Nemotron
- **Environment Variables:**
  - `NVIDIA_API_KEY`: Configured in `backend/.env`.
  - `NVIDIA_BASE_URL`: `https://integrate.api.nvidia.com/v1` (Default in `backend/config/settings.py` and `backend/.env.example`).
  - `NVIDIA_TEXT_MODEL`: `nvidia/nemotron-3.5-lightning-30b-a3b` (Configured in `settings.py`).
- **Services Utilizing Nemotron:**
  1. `NemotronDialogueService` (`backend/interviews/services/dialogue_service.py`):
     - Handles active candidate turns.
     - Strips model `<thought>` / reasoning tokens using `strip_reasoning()`.
     - Enforces structured JSON output matching `DialogueTurnResponse`.
     - Request timeout: **45 seconds** connect/read timeout.
  2. `EvaluationService` (`backend/evaluations/services/evaluation_service.py`):
     - Executes post-interview grading across 4 rubric dimensions (Technical Knowledge, System Design, Problem Solving, Communication).
     - Validates against `EvaluationOutputSchema` (Pydantic v2).
     - Request timeout: **60 seconds** connect/read timeout.

### 2.2 Deepgram STT
- **Environment Variables:**
  - `DEEPGRAM_API_KEY`: Defined in `.env.example`, currently **unset** in `backend/.env`.
  - `STT_PROVIDER`: Set or defaulted to `mock`. Switching to `deepgram` requires setting `STT_PROVIDER=deepgram` and providing `DEEPGRAM_API_KEY`.
- **Implementation Details (`backend/integrations/speech/stt/deepgram.py`):**
  - Endpoint: `https://api.deepgram.com/v1/listen?model=nova-3&language=en-IN&smart_format=true&punctuate=true`
  - Authentication: Header `Authorization: Token {api_key}`
  - Accepted Payload: Raw audio bytes streamed in HTTP POST body with appropriate `Content-Type`.
  - Max File Size: 25 MB (`MAX_AUDIO_SIZE_BYTES`).
  - Allowed Formats: `audio/wav`, `audio/webm`, `audio/ogg`, `audio/mp3`, `audio/m4a`.
  - Timeout: **10 seconds**.

### 2.3 ElevenLabs TTS
- **Environment Variables:**
  - `ELEVENLABS_API_KEY`: Defined in `.env.example`, currently **unset** in `backend/.env`.
  - `TTS_PROVIDER`: Set or defaulted to `mock`. Switching to `elevenlabs` requires setting `TTS_PROVIDER=elevenlabs` and providing `ELEVENLABS_API_KEY`.
- **Implementation Details (`backend/integrations/speech/tts/elevenlabs.py`):**
  - Endpoint: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
  - Default Voice ID: `21m00Tcm4TlvDq8ikWAM` (Rachel).
  - Model: `eleven_multilingual_v2`.
  - Authentication: Header `xi-api-key: {api_key}`.
  - Output Format: `audio/mpeg` (or WAV).
  - Timeout: **15 seconds**.

### 2.4 OpenAI (Question Generation)
- **Environment Variables:**
  - `OPENAI_API_KEY`: Configured in `backend/.env`.
  - `OPENAI_TEXT_MODEL`: `gpt-4o-mini`.
- **Service:**
  - `QuestionGeneratorService` (`backend/interviews/services/question_generator.py`) uses OpenAI structured outputs (`client.beta.chat.completions.parse`) with `InterviewPlanSchema` to generate questions from JD and resume.

---

## 3. Architecture & Audio Pipeline Inspection

```
Candidate Browser (CandidateInterviewPage.jsx)
   │
   │ 1. Records chunk (audio/webm;codecs=opus) via MediaRecorder
   │ 2. POST /api/v1/candidate/submit-turn/ (multipart/form-data)
   ▼
Django Backend (candidate_views.py - CandidateSubmitTurnView)
   │
   ├─► SpeechProviderFactory.get_stt_provider()
   │      │
   │      └─► DeepgramSTTProvider.transcribe(audio_file)
   │             POST https://api.deepgram.com/v1/listen (Token Auth)
   │             ◄── Returns transcript JSON: { text, confidence, duration }
   │
   ├─► NemotronDialogueService.process_candidate_turn(...)
   │      POST https://integrate.api.nvidia.com/v1/chat/completions (Bearer Auth)
   │      ◄── Returns structured response: { interviewer_message, status, score }
   │
   └─► HTTP 200 Response: { candidate_transcript, interviewer_message, status }
          │
Candidate Browser Receives Message
   │
   │ 3. POST /api/v1/candidate/synthesize-speech/ { message }
   ▼
Django Backend (candidate_views.py - CandidateSynthesizeSpeechView)
   │
   ├─► SpeechProviderFactory.get_tts_provider()
   │      │
   │      └─► ElevenLabsTTSProvider.synthesize(text)
   │             POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id} (xi-api-key)
   │             ◄── Returns audio/mpeg binary stream
   │
   └─► HTTP 200 StreamingHttpResponse: binary audio/mpeg
          │
Candidate Browser Plays Audio via HTML5 Audio()
```

### Key Architectural Findings:
1. **Synchronous Voice Turns vs Async Evaluations:**
   - Both STT and Dialogue Turn generation execute within `CandidateSubmitTurnView` synchronously to minimize candidate conversational latency.
   - Speech synthesis is triggered immediately after via a secondary synchronous call `CandidateSynthesizeSpeechView`.
   - Comprehensive multi-dimension evaluation (`generate_evaluation_task`) and plan generation (`generate_plan_task`) run asynchronously via Celery workers with transactional integrity.
2. **Audio Codec Matching:**
   - Browser records `audio/webm;codecs=opus` (with fallback to `audio/ogg` or `audio/wav`).
   - `BaseSTTProvider.SUPPORTED_CONTENT_TYPES` explicitly includes `audio/webm`.
   - Deepgram Nova-3 natively parses WebM Opus containers without server-side transcoding.
3. **Prompt Injection & Reasoning Token Defense:**
   - User transcripts are wrapped in boundary tags `<candidate_response>` in `NemotronDialogueService`.
   - NVIDIA Nemotron thinking blocks (`<thought>...</thought>`) are stripped before parsing JSON to prevent formatting corruption.

---

## 4. Mock vs. Live Comparison

| Capability | Mock Implementation | Live Provider Implementation | Readiness Status |
| :--- | :--- | :--- | :--- |
| **STT Engine** | `MockSTTProvider`: Returns deterministic canned strings or reverse echoes. | `DeepgramSTTProvider`: Hits `api.deepgram.com/v1/listen` with Nova-3 model. | **READY** (Requires `DEEPGRAM_API_KEY`) |
| **TTS Engine** | `MockTTSProvider`: Returns a 1-second silent WAV header byte array. | `ElevenLabsTTSProvider`: Hits `api.elevenlabs.io/v1/text-to-speech` with Multilingual v2. | **READY** (Requires `ELEVENLABS_API_KEY`) |
| **Dialogue Engine** | Mock test fixture or direct call. | `NemotronDialogueService`: Hits `integrate.api.nvidia.com/v1/chat/completions`. | **READY** (`NVIDIA_API_KEY` present) |
| **Evaluation Engine** | Mock evaluation records. | `EvaluationService`: Hits Nemotron with multi-rubric evaluation prompt. | **READY** (`NVIDIA_API_KEY` present) |
| **Audio Format Handling** | Validates MIME type only. | Deepgram receives and parses raw WebM Opus stream directly. | **READY** (Tested MIME types align) |
| **Error Fallback** | Deterministic errors. | Returns HTTP 502 / `STTError` / `TTSError` / `AIServiceError` with structured logs. | **READY** (Exceptions caught and logged) |

---

## 5. Implementation Gaps and Blockers

### ⚠️ Blocker 1: Missing Deepgram and ElevenLabs Keys in `backend/.env`
- In `backend/.env`, only `NVIDIA_API_KEY`, `OPENAI_API_KEY`, and `DATABASE_URL` are populated.
- `DEEPGRAM_API_KEY` and `ELEVENLABS_API_KEY` are not set.
- `STT_PROVIDER` and `TTS_PROVIDER` are currently set/defaulted to `mock`.
- **Resolution required before live interview:**
  ```env
  STT_PROVIDER=deepgram
  DEEPGRAM_API_KEY=your_live_deepgram_key
  TTS_PROVIDER=elevenlabs
  ELEVENLABS_API_KEY=your_live_elevenlabs_key
  ```

### ⚠️ Warning 2: Provider Discrepancy (OpenAI vs NVIDIA)
- `interviews/services/question_generator.py` uses OpenAI's Python SDK (`OPENAI_API_KEY` / `gpt-4o-mini`) for plan generation.
- `interviews/services/dialogue_service.py` and `evaluations/services/evaluation_service.py` use NVIDIA Nemotron.
- *Status:* Both API keys (`OPENAI_API_KEY` and `NVIDIA_API_KEY`) are already set in `.env`, so this will function without failure. However, for complete architectural consistency, plan generation could eventually be migrated to Nemotron.

### ⚠️ Warning 3: Turn Latency Budget
- For each candidate turn:
  - Deepgram STT HTTP POST: ~300ms - 800ms
  - Nemotron Dialogue HTTP POST: ~1000ms - 2200ms
  - Total `submit-turn` latency: ~1.3s - 3.0s
  - ElevenLabs TTS HTTP POST: ~800ms - 1500ms
  - Total latency before candidate hears audio: **~2.1s - 4.5s**
- *Mitigation:* The frontend UI displays an active thinking spinner (`Interviewer is thinking...` and `Synthesizing audio...`) to provide immediate feedback to the candidate.

---

## 6. API Call Count & Cost Estimates per 30-Minute Interview

Estimates based on an interview with **8 dialogue turns**:

1. **Question Generation (1 call, asynchronous on plan creation):**
   - OpenAI `gpt-4o-mini`: ~1.5k input tokens, ~1k output tokens (~$0.001)
2. **Speech-to-Text (8 calls):**
   - Deepgram Nova-3: 8 turns × ~30 seconds of audio = ~4 minutes audio (~$0.017)
3. **Dialogue Turns (8 calls):**
   - NVIDIA Nemotron: 8 turns × (~2.5k context tokens + 150 output tokens) = ~20k input, ~1.2k output tokens (~$0.01 - $0.03 depending on NIM tier)
4. **Speech Synthesis (8 calls):**
   - ElevenLabs: 8 turns × ~40 words (~200 characters) = ~1,600 characters (~$0.04 - $0.08)
5. **Evaluation Generation (1 call, asynchronous upon interview completion):**
   - NVIDIA Nemotron: ~5k context tokens (full transcript + rubric + JD), ~1.5k output tokens (~$0.005)
6. **Total Estimated Cost Per Complete Interview:** **<$0.15 USD**.

---

## 7. Recommended Live Validation Sequence (Phase 10.7 Preview)

When proceeding to live testing:
1. **Isolated Provider Probing:** Execute a one-line curl or python script test for each provider (Deepgram, ElevenLabs, NVIDIA) to verify credential validity and rate limits without affecting DB state.
2. **Single Audio Turn Test:** Use a test candidate session with a short 5-second audio sample to confirm STT transcription accuracy and WebM compatibility.
3. **Single Speech Synthesis Test:** Synthesize a single sentence through ElevenLabs to verify audio codec playback in Chrome/Edge/Firefox.
4. **Complete Controlled Interview:** Conduct a 3-turn live voice interview from the candidate browser page.
5. **Evaluation Verification:** Trigger interview completion and verify that Celery generates the evaluation report with accurate evidence citations.

---

## 8. Exact Service Launch Commands

To execute the application locally with full live provider support:

```bash
# 1. WSL Redis Server
wsl sudo service redis-server start

# 2. Django Backend (Port 8000)
cd backend
..\.venv\Scripts\python.exe manage.py runserver 8000

# 3. Celery Worker (Task execution)
cd backend
..\.venv\Scripts\celery.exe -A config worker -l info -P solo

# 4. Vite Frontend (Port 5173)
cd frontend
npm run dev
```

---

## 9. Final Preflight Audit Verdict

**VERDICT: READY WITH WARNINGS**

The codebase is technically and architecturally ready for live provider testing. The data contracts, audio encoding parameters, error boundaries, and API integrations are sound. Once valid API keys for Deepgram and ElevenLabs are provided in `backend/.env`, Phase 10.7 live validation may proceed.

