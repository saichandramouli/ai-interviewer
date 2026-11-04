# Candidate Interview Invitation Email Integration — Implementation Report

## 1. Overview
The **Candidate Interview Invitation Email Integration** feature automatically and asynchronously emails secure, expiring, single-candidate interview links directly to the candidate's registered email address whenever a recruiter generates or resends a candidate interview link.

---

## 2. Architecture & Components

### 2.1 Backend Email Configuration & Environment
- **Settings**: Configured standard Django email settings in `backend/config/settings.py` (`EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`).
- **Defaults**: Defaults to the console email backend (`django.core.mail.backends.console.EmailBackend`) when in development / debug mode to prevent accidental live sends, while allowing standard SMTP in production.
- **Environment**: Updated `.env.example` with the necessary email parameter placeholders (no secrets hardcoded).

### 2.2 Model Schema & Delivery Tracking
Extended `CandidateInterviewAccessToken` in `backend/interviews/models.py` with tracking attributes (Migration `0005_candidateinterviewaccesstoken_delivery_error_and_more.py`):
- `delivery_status`: `pending`, `sent`, `failed` (default `pending`).
- `sent_at`: Timestamp when the email was successfully accepted by the email provider.
- `recipient_email`: The registered candidate email address at dispatch time.
- `delivery_error`: Sanitized delivery failure descriptions if delivery encounters an unrecoverable failure.

### 2.3 Email Templates & Builders
Created `backend/interviews/services/email_service.py`:
- `build_candidate_invitation_subject(job_title)`: Formats standard subject `"Invitation to Attend Your AI Interview: <Job Title>"`.
- `build_candidate_invitation_body(...)`: Plain-text fallback providing candidate greeting, organization context, secure link, expiration timestamp, hardware requirements (mic/speakers), browser requirements, and support message.
- `build_candidate_invitation_html(...)`: Styled HTML email with responsive typography, CTA button, and clear expiration notices.
- **Security Guarantee**: Does not contain internal evaluation scores, recruiter notes, model outputs, or internal IDs.

### 2.4 Asynchronous Celery Email Delivery Task
Added `send_candidate_invitation_email_task` in `backend/interviews/tasks.py`:
- **Idempotency**: Inspects token status before dispatch; exits immediately if `delivery_status == 'sent'`.
- **Validation**: Enforces candidate consent and ensures tokens are not expired or revoked before sending.
- **Bounded Retries & Exponential Backoff**: Retries up to 3 times with exponential backoff (`countdown=15 * 2^retries`) on transient SMTP/network exceptions.
- **Privacy & Sanitization**: Never logs raw tokens or complete query strings in task logs.

### 2.5 Recruiter Endpoints
Enhanced `InterviewViewSet` in `backend/interviews/views.py`:
- `POST /api/v1/interviews/{id}/generate-candidate-link/`: Generates candidate access token, hashes it, constructs the frontend URL, and asynchronously dispatches the Celery email task.
- `POST /api/v1/interviews/{id}/resend-candidate-link/`: Invalidates older unused tokens, generates a fresh link, and dispatches the invitation email.
- `GET /api/v1/interviews/{id}/candidate-link-status/`: Returns current delivery status (`pending`, `sent`, `failed`), candidate recipient email, expiration date, and validity state.

---

## 3. Frontend Recruiter UI
- **Candidate Invite Modal**: Created `frontend/src/components/CandidateInviteModal.jsx` featuring:
  - Candidate email display.
  - Delivery badge (`SENT`, `PENDING`, `FAILED`).
  - Active / Expired / Revoked token status indicators.
  - Copy Link button with one-click clipboard feedback.
  - "Generate & Send Invite" / "Resend Invitation Email" actions with loading spinners.
- **Interviews Page Integration**: Added an "Invite" action button directly to the interviews table in `frontend/src/pages/InterviewsPage.jsx` for all active interviews.

---

## 4. Test Verification
- **Backend Tests**: Added comprehensive test suite `backend/interviews/test_candidate_invitation_email.py` (9 tests covering automated queuing, email contents, idempotency, expired token guards, resending, and recruiter authorization).
  - Backend test suite: **157 passed** (with 0 regressions across existing suites).
- **Frontend Tests**: Added `frontend/src/pages/__tests__/CandidateInviteModal.test.jsx`.
  - Frontend test suite: **38 passed** across 10 test files.
- **Vite Build**: Production bundle succeeded with zero errors (`dist/index.html` built cleanly).

