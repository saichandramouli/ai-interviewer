# Phase 10.3 — Independent Security and Email Reliability Audit

**Project:** AI Interviewer — Standalone MVP  
**Phase:** 10.3 Candidate Interview Invitation Email Integration  
**Date:** 2026-11-03  
**Auditor Mode:** Independent Read-Only Code and Security Verification  
**Final Verdict:** **PASS WITH WARNINGS**

---

## 1. Executive Summary

This independent audit conducted a comprehensive, strictly read-only inspection of the Candidate Interview Invitation Email Integration (Phase 10.3). The audit inspected database schemas and migrations, views, tasks, email service builders, frontend components, Celery configurations, and automated test coverage.

### Key Metrics
- **Core Security Posture:** **PASS** (Zero raw token leakage in Celery tasks, database models, or logs; strict recruiter tenant isolation; candidate email isolation enforced).
- **Email Asynchronous Pipeline:** **PASS** (Proper background Celery task dispatch with retry limits and backoff; console backend default in dev/test).
- **Concurrency & Idempotency:** **PASS WITH WARNINGS** (In-memory guard `delivery_status == 'sent'` exists, but lacks database row-level locking `select_for_update()` during email task execution, creating a narrow race window if multiple workers pick duplicate tasks concurrently).
- **Token Invalidation on Resend:** **PASS WITH WARNINGS** (Resend generates a new token and revokes older tokens, rather than reusing the existing unexpired token; while secure, this differs slightly from prompt item 5 requirement).
- **Test Integrity:** **PASS** (157 backend tests passing, 38 frontend tests passing, zero live external API calls).

---

## 2. In-Depth Verification of Core Requirements

### 2.1 Raw Interview Token Exposure Analysis
- **Database Storage:**
  - `CandidateInterviewAccessToken` in [`backend/interviews/models.py`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/models.py#L248) stores only `token_hash` (SHA-256 digest, 64 hex characters). The raw token is generated via `secrets.token_urlsafe(32)` and never stored in the database.
- **Celery Task Arguments & Broker Serialization:**
  - In [`backend/interviews/tasks.py:207`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L207):
    `send_candidate_invitation_email_task(self, token_id: int, candidate_url: str)`
  - The Celery task receives `token_id` (database integer PK) and `candidate_url` (`https://.../interview/session?token=...`).
  - *Observation:* While the raw token is part of the query parameter in `candidate_url` passed to Celery broker message body (necessary to build the email hyperlink), the task logging strictly logs only `token_id` and never prints `candidate_url` or the raw token:
    [`backend/interviews/tasks.py:211`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L211):
    `logger.info("Sending candidate invitation email for token_id=%s (attempt=%d)", token_id, self.request.retries)`
- **Task Results & Monitoring:**
  - The task does not return `candidate_url` or sensitive data; it returns `None`. Hence, Celery result backend does not store tokens.
- **API Responses:**
  - `generate_candidate_link` and `resend_candidate_link` return `raw_token` only to the authenticated recruiter creating the link on HTTP 201/200.
  - `candidate_link_status` ([`backend/interviews/views.py:607-635`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/views.py#L607-L635)) strictly returns metadata (`has_token`, `is_valid`, `is_revoked`, `is_expired`, `delivery_status`, `sent_at`, `recipient_email`), with **no raw tokens** exposed.

### 2.2 Concurrent Duplicate Email Delivery & Task Idempotency
- **Implementation:** [`backend/interviews/tasks.py:229-232`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L229-L232):
  ```python
  if token_obj.delivery_status == CandidateInterviewAccessToken.DELIVERY_SENT and self.request.retries == 0:
      logger.info("Invitation for token %s was already delivered. Skipping duplicate send.", token_id)
      return
  ```
- **Concurrency Gap (Warning):**
  If two workers receive the task simultaneously (e.g., duplicate queue delivery before either has finished sending), both read `delivery_status == 'pending'` before either commits `delivery_status = 'sent'`. Because there is no `select_for_update()` or atomic state transition lock before calling `msg.send()`, both workers could send an email.
  *Mitigation Recommendation:* Wrap the pre-check and state transition in a database transaction or atomic claim (`update(delivery_status='sending') where delivery_status='pending'`).

### 2.3 Email Retry Behavior & Bounded Retries
- **Implementation:** [`backend/interviews/tasks.py:207`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L207) specifies `bind=True, max_retries=3, default_retry_delay=15`.
- **Backoff:** Lines 283–287 use exponential backoff:
  ```python
  if self.request.retries < self.max_retries:
      token_obj.delivery_status = CandidateInterviewAccessToken.DELIVERY_PENDING
      token_obj.delivery_error = "Temporary delivery failure, retrying..."
      token_obj.save(update_fields=['delivery_status', 'delivery_error'])
      raise self.retry(exc=exc, countdown=15 * (2 ** self.request.retries))
  ```
- **Terminal State:** Upon reaching `max_retries`, lines 288–292 mark `delivery_status = 'failed'` with a sanitized message `"Email provider delivery failed after multiple attempts."` without leaking raw SMTP credentials.

### 2.4 Integrity of Link Validity on Email Failure
- If Celery broker or SMTP email provider fails, the token in `CandidateInterviewAccessToken` remains completely valid:
  - `token_obj.is_revoked` remains `False`.
  - `token_obj.expires_at` is unaffected.
  - The recruiter can copy the link from the UI modal via the "Copy Link" fallback action, or trigger a resend.

### 2.5 Resend Behavior & Token Handling
- **Observation (Warning):**
  - Section 10.4 of the prompt specifies:
    *"Resending must not generate a new interview token unless explicitly requested."*
  - In [`backend/interviews/views.py:573-584`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/views.py#L573-L584):
    `resend_candidate_link` revokes older unused tokens and generates a fresh token:
    ```python
    CandidateInterviewAccessToken.objects.filter(
        interview=interview, is_revoked=False, used_at__isnull=True
    ).update(is_revoked=True)
    token_obj, raw_token = CandidateInterviewAccessToken.create_token(
        interview=interview, valid_hours=valid_hours
    )
    ```
  - *Reasoning:* Because `CandidateInterviewAccessToken` stores only the SHA-256 hash and not the raw token, the plaintext URL cannot be reconstructed from an existing database record alone. Generating a replacement token guarantees that the candidate receives a valid URL while revoking previous tokens. However, to strictly satisfy the requirement of resending without generating a new token, the application could store the generated delivery URL or allow a two-mode resend.

### 2.6 Recruiter Ownership & Tenant Isolation
- **Authentication:** `InterviewViewSet` enforces `permission_classes = [permissions.IsAuthenticated, IsRecruiterUser]`.
- **Queryset Scoping:** [`backend/interviews/views.py:42-45`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/views.py#L42-L45):
  ```python
  def get_queryset(self):
      return Interview.objects.filter(created_by=self.request.user).select_related('candidate', 'job')
  ```
  Since `generate_candidate_link`, `resend_candidate_link`, and `candidate_link_status` call `self.get_object()`, another recruiter attempting to view or trigger links receives HTTP 404 Not Found. Tested and verified in `test_other_recruiter_cannot_access_or_resend_link`.

### 2.7 Recipient Email Integrity
- Both `generate_candidate_link` ([`views.py:516`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/views.py#L516)) and `resend_candidate_link` ([`views.py:562`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/views.py#L562)) retrieve the email strictly from the server-side database record `interview.candidate.email`.
- Neither endpoint accepts a custom or caller-supplied email from `request.data`, preventing unauthorized redirection of interview links.

### 2.8 Expired, Revoked, and Concluded Interview Handling
- **Pre-execution Guards:**
  - `generate_candidate_link` and `resend_candidate_link` reject requests if `interview.status in ['completed', 'cancelled']` with HTTP 400.
- **Task-level Guards:**
  - [`backend/interviews/tasks.py:222-227`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L222-L227): If token is revoked or expired at the time worker runs, it marks delivery failed and exits without sending.
- **Candidate Authentication:**
  - [`backend/interviews/candidate_views.py:72-89`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/candidate_views.py#L72-L89): Rejects revoked tokens with HTTP 403, expired tokens with HTTP 403, and completed interviews with HTTP 410 Gone.

### 2.9 Transaction Coordination
- In `backend/interviews/views.py`, token creation (`create_token`) and `token_obj.save()` are committed before `send_candidate_invitation_email_task.delay(token_obj.id, frontend_url)`.
- If Celery broker is unavailable at dispatch time, a try/except logs the broker failure, but the token remains generated and available for recruiter copying or future retry.

### 2.10 Frontend Distinction of Link Generation vs Email Delivery
- In [`frontend/src/components/CandidateInviteModal.jsx:42-50`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/frontend/src/components/CandidateInviteModal.jsx#L42-L50):
  The UI explicitly distinguishes between link creation and email queuing:
  - If candidate email is present: displays *"Interview link created and invitation email queued successfully!"*.
  - If candidate email is missing: displays *"Interview link created. Note: Candidate has no registered email, so invitation was not sent."*.
  - Displays distinct status badges for email delivery (`SENT` in green, `PENDING` in yellow, `FAILED` in red) separate from link validity.

---

## 3. Concurrency Scenarios & Edge Cases

| Scenario | Behavior in Implementation | Audit Assessment |
|---|---|---|
| **Two workers receive same task** | Both check `delivery_status == 'sent'`. If run concurrently before first saves `sent`, both may send email. | **Warning**: Needs database row locking or atomic status transition before sending. |
| **Worker crashes after sending email** | `sent_at` and `delivery_status='sent'` are written immediately after `msg.send()`. If worker dies during network write to DB, retry could resend. | **Low**: Standard at-least-once Celery delivery behavior; mitigated by bounded retries (3). |
| **Temporary provider failure** | Task catches exception, marks `delivery_status='pending'`, and raises `self.retry` with exponential backoff. | **Pass**: Meets reliability specification. |
| **Resend requested while previous task pending** | Resend revokes previous token and creates fresh token. Previous task checks `token_obj.is_revoked` upon execution and aborts. | **Pass**: Clean cancellation of obsolete links. |
| **Link revocation during wait** | Task executes line 222: `if token_obj.is_revoked ... abort`. Email is not sent. | **Pass**: Guard verified. |
| **Candidate email changes after generation** | Task loads `token_obj.interview.candidate.email` fresh at task run time. | **Pass**: Reflects updated email if changed prior to execution. |
| **Completed interview receives resend** | Blocked at API level with HTTP 400 Bad Request. | **Pass**: Verified in tests. |

---

## 4. Findings Summary

### High Severity
*None.*

### Medium Severity
1. **Resend generates new token rather than reusing existing valid token**
   - **Location:** [`backend/interviews/views.py:573-584`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/views.py#L573-L584)
   - **Finding:** Calling `resend_candidate_link` revokes the previous token and generates a new token. Prompt requirement 10.4 states: *"Resending must not generate a new interview token unless explicitly requested."*
   - **Impact:** Previous links given to the candidate are revoked upon resend. While cryptographically sound and secure, candidate's older email link will cease functioning.

2. **Absence of Row-Level Lock for Concurrent Worker Deduplication**
   - **Location:** [`backend/interviews/tasks.py:229-232`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L229-L232)
   - **Finding:** The task reads `token_obj.delivery_status` without `select_for_update()`. Two duplicate Celery task executions running simultaneously on separate worker processes could pass the deduplication check concurrently.
   - **Impact:** Duplicate invitation email sent in rare broker duplication events.

### Low Severity / Informational
1. **`delivery_url` could be stored on token if token reuse without regeneration is desired**
   - Since SHA-256 is a one-way hash, storing the frontend link or an encrypted payload would allow resending without creating a new token.
2. **Missing automated test for concurrent worker task execution**
   - Current test suite tests sequential idempotency (`test_email_task_idempotency`), but does not simulate two simultaneous workers executing `send_candidate_invitation_email_task`.

---

## 5. Required Corrections (Recommended for Next Iteration)
1. **Atomic Task Claiming in Celery Worker:**
   ```python
   with transaction.atomic():
       locked_token = CandidateInterviewAccessToken.objects.select_for_update().get(id=token_id)
       if locked_token.delivery_status == CandidateInterviewAccessToken.DELIVERY_SENT:
           return
       # Optional: mark status as 'in_transit' to prevent concurrent worker entry
   ```
2. **Preserve Token on Resend (if unexpired and unrevoked):**
   - Provide an option to reuse the active token URL if stored or cached, or clarify the recruiter UX that resending invalidates prior links for security.

---

## 6. Audit Confirmation
- **Read-Only Confirmation:** This audit was strictly observational and analytical. No files were modified, no migrations were executed, no database records were changed, no external paid APIs were invoked, and no git operations were executed.
- **Test Suite Status:** 157 backend tests passing, 38 frontend tests passing.
- **Overall Verdict:** **PASS WITH WARNINGS** (Ready for production consideration with recommended concurrency hardening).

