# Phase 10.3.1 — Email Delivery Concurrency and Resend Reliability Hardening Report

**Project:** AI Interviewer — Standalone MVP  
**Phase:** 10.3.1 Reliability Hardening  
**Date:** 2026-11-03  
**Status:** **COMPLETE & FULLY VERIFIED**

---

## 1. Overview & Objectives Addressed

Phase 10.3.1 resolved the two medium-severity findings identified during the independent Phase 10.3 audit:
1. **Concurrent Duplicate Delivery Prevention**: Implemented database-backed atomic task claiming with row-level locking (`select_for_update()`), an intermediate `sending` state, and a crash-recovery bounded lease (180 seconds).
2. **Deterministic Resend Semantics**:
   - Ordinary resends reuse the existing active token URL without generating a replacement token and without invalidating the existing link.
   - Designed and integrated an authenticated symmetric encryption envelope (`interviews.services.token_crypto`) to securely persist the generated link without storing raw tokens in plaintext or weakening SHA-256 token hashing.
   - Introduced an explicit recruiter-initiated replacement action (`replace_candidate_link`) with recruiter confirmation dialogues in the UI.

---

## 2. Technical Architecture & Modifications

### 2.1 Model Schema Updates (`CandidateInterviewAccessToken`)
Migration `0006_candidateinterviewaccesstoken_delivery_started_at_and_more.py` added:
- `DELIVERY_SENDING = 'sending'`: Intermediate state preventing parallel Celery workers from claiming or delivering the same invitation.
- `delivery_started_at`: Timestamp tracking when the task claim began, enabling bounded lease recovery if a worker process crashes mid-flight.
- `encrypted_candidate_url`: Authenticated ciphertext storing the frontend candidate session URL.

### 2.2 Authenticated URL Crypto Service (`interviews.services.token_crypto`)
- Pure Python standard library implementation (`hashlib`, `hmac`, `os.urandom`, `base64`).
- Derives distinct 256-bit encryption and authentication keys from `settings.SECRET_KEY` using domain separation.
- Uses PRF-CTR stream encryption with an Encrypt-then-MAC HMAC-SHA256 authenticated envelope.
- Constant-time MAC comparison prevents timing side channels.
- **Security Guarantee:** Raw tokens are never stored in plaintext, never exposed in database columns, and never logged. SHA-256 token hashing remains the authoritative candidate session lookup mechanism.

### 2.3 Atomic Task Claiming & Worker Concurrency (`send_candidate_invitation_email_task`)
- **Row-Level Lock:** Uses `select_for_update()` inside a compact `transaction.atomic()` block.
- **Deduplication Check:** If `delivery_status == 'sent'`, worker exits immediately.
- **Active Lease Check:** If `delivery_status == 'sending'` and `delivery_started_at > now - 180s`, worker exits gracefully without duplicate sending.
- **Crash Recovery:** If a prior worker died and the lease expired (`> 180s`), the task re-claims the record and delivers the email.
- **Lock Isolation:** Transaction commits and database locks release **before** external email dispatch (`msg.send()`).

### 2.4 Recruiter API Endpoints (`InterviewViewSet`)
1. `generate_candidate_link`: Generates random URL-safe token, hashes it with SHA-256, encrypts the candidate URL into `encrypted_candidate_url`, and queues the email task.
2. `resend_candidate_link`: Decrypts `encrypted_candidate_url` of the active token, resets delivery state to `pending`, and dispatches Celery email task **without** creating a new token or revoking the active token.
3. `replace_candidate_link`: Explicit endpoint that revokes previous tokens and generates a fresh replacement token.
4. `candidate_link_status`: Returns current delivery state (`pending`, `sending`, `sent`, `failed`), candidate email, and token validity state.

### 2.5 Recruiter Frontend UI (`CandidateInviteModal.jsx`)
- Clearly presents link status:
  - Active & Valid vs Expired vs Revoked.
  - Delivery badge: `SENDING` (with spinner), `SENT`, `FAILED`, `PENDING`.
- Separate distinct action buttons:
  - **"Resend Existing Link"**: Retries delivery without altering candidate tokens.
  - **"Replace Link"**: Triggers an alert confirmation warning the recruiter that older links will be revoked before creating a replacement link.
- "Copy Link" fallback clipboard button.

---

## 3. Automated Test Verification

### 3.1 Hardening Test Suite (`test_phase10_3_1_hardening.py`)
- `test_ordinary_resend_preserves_existing_token_without_generating_new_one`: PASSED
- `test_explicit_replace_revokes_prior_token_and_creates_new_token`: PASSED
- `test_concurrent_worker_claiming_prevents_duplicate_send`: PASSED
- `test_stale_sending_state_lease_recovery`: PASSED
- `test_duplicate_task_execution_after_sent_does_not_send_again`: PASSED
- `test_resend_fails_if_token_expired`: PASSED
- `test_resend_fails_if_token_revoked`: PASSED
- `test_other_recruiter_cannot_replace_or_resend`: PASSED
- `test_raw_token_never_stored_in_database`: PASSED

### 3.2 Regression Verification
- Combined Email Suites (`test_candidate_invitation_email.py` + `test_phase10_3_1_hardening.py`): **18 passed** in 11.92s.
- Full Frontend Suite: **38 passed** across 10 test suites (Vitest).
- Frontend Build: `vite build` completed successfully (`dist/assets/index-CDtliRvA.js`).
- Database Consistency: `manage.py migrate --check` returned 0 unapplied migrations.
- System Checks: `manage.py check` identified 0 issues.

---

## 4. Known Limitations & Notes
- Bounded lease recovery is set to 3 minutes (180 seconds). In environments with severe email gateway latency exceeding 3 minutes, delivery could trigger re-claiming; however, Celery task timeout is configured to 120s max, ensuring operations finish within the lease.

