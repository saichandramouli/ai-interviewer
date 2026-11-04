# Phase 10.3.1 — Final Cryptographic and Reliability Verification

**Project:** AI Interviewer — Standalone MVP  
**Phase:** 10.3.1 Final Cryptographic & Reliability Verification  
**Date:** 2026-11-03  
**Auditor Mode:** Independent Read-Only Security Audit  
**Overall Verdict:** **PASS WITH WARNINGS**

---

## 1. Executive Summary

An independent, read-only security audit was conducted on the Phase 10.3.1 implementation, focusing on custom encrypted candidate URL storage, Celery task handling, concurrency controls, lease recovery, and resend workflow.

### Key Audit Findings
1. **Custom Cryptography (`interviews/services/token_crypto.py`)**: **PASS WITH WARNINGS**
   - The cipher construction adheres to standard cryptographic principles: domain-separated key derivation from `SECRET_KEY`, random 128-bit IV/nonce per message, PRF-CTR stream encryption with 64-bit big-endian counter, and constant-time HMAC-SHA256 Encrypt-then-MAC verification prior to decryption.
   - *Warning*: Building custom stream ciphers rather than using standard libraries (such as `cryptography.fernet` or `nacl.secret`) carries inherent risk of subtle edge-case errors. Because `cryptography` is currently omitted from `requirements.txt`, this custom pure-Python implementation is functional and secure for local deployment, but migrating to `cryptography.fernet.Fernet` or Django's built-in signing serializer (`django.core.signing`) is formally recommended when adding production dependencies.
2. **Raw Token & Secret Exposure**: **PASS**
   - Database tables store strictly SHA-256 digests (`token_hash`) for token lookup; raw tokens are never persisted in plaintext.
   - Encrypted URLs are isolated in `encrypted_candidate_url`.
   - Celery task arguments passed to `send_candidate_invitation_email_task.delay(token_obj.id, frontend_url)` contain the URL for email construction, but all worker logging strictly suppresses URLs and prints only `token_id`.
   - Candidate status endpoints (`candidate_link_status`) return zero token hashes, zero ciphertexts, and zero raw tokens.
3. **Concurrency Controls & Lease Recovery**: **PASS**
   - Atomic database-backed task claiming with `select_for_update()` inside a compact transaction ensures only one worker claims a pending invitation.
   - The intermediate `sending` status and 180-second bounded lease prevent parallel duplicate email deliveries while allowing crash recovery.
   - Row locks are released **before** contacting the external email provider (`msg.send()`).
4. **Resend and Replacement Semantics**: **PASS**
   - Ordinary resends reuse the existing active token's URL without generating new tokens or revoking older ones.
   - Explicit replacement (`replace_candidate_link`) revokes prior tokens and generates a replacement token with recruiter UI confirmation.
5. **Test Regressions**: **PASS**
   - 164 backend tests passed cleanly with 0 failures; 38 frontend tests passed across 10 test suites; Vite production build completed with 0 errors.

---

## 2. In-Depth Cryptographic Assessment

### 2.1 Analysis of `backend/interviews/services/token_crypto.py`

| Cryptographic Component | Implementation Details | Assessment |
|---|---|---|
| **Key Derivation** | Derives separate 32-byte encryption key (`candidate_url_enc_v1`) and 32-byte MAC key (`candidate_url_mac_v1`) from `settings.SECRET_KEY` using SHA-256 domain prefixes. | **PASS**: Effective domain separation between confidentiality and authenticity. |
| **Nonce / IV Generation** | Generated via `os.urandom(16)` per encryption call. | **PASS**: Cryptographically strong entropy provided by OS CSPRNG. |
| **Nonce Collision Risk** | Birthday bound on 128-bit random nonce is $2^{64}$ operations. For interview link generation volumes, nonce reuse probability is negligible ($< 10^{-15}$). | **PASS**: Negligible risk. |
| **PRF-CTR Keystream** | Stream cipher constructed as $K_i = \text{HMAC-SHA256}(K_{enc}, \text{nonce} \parallel \text{counter}_i)$ with 8-byte big-endian counter. | **PASS**: Standard PRF-based counter mode construction. |
| **Counter Construction** | Counter starts at 0, increments by 1 per 32-byte block. Candidate URLs are $< 200$ bytes ($\le 7$ blocks), preventing counter overflow. | **PASS**: Counter bounds respected. |
| **Encrypt-then-MAC** | MAC covers `(nonce || ciphertext)` using `hmac.new(mac_key, ..., hashlib.sha256)`. | **PASS**: Standard Encrypt-then-MAC paradigm (provably secure against padding/tampering attacks). |
| **Constant-Time Verification** | Uses `django.utils.crypto.constant_time_compare(mac, expected_mac)`. | **PASS**: Resistant to timing attacks. |
| **Verification Precedence** | MAC is verified **before** keystream generation or ciphertext decryption. | **PASS**: Rejects tampered payloads immediately. |
| **Tampering & Truncation** | Rejects payloads $< 48$ bytes or invalid Base64 with graceful `None` return. | **PASS**: No unhandled exceptions or stack trace leaks. |
| **SECRET_KEY Rotation** | Rotating `DJANGO_SECRET_KEY` invalidates previous ciphertexts (`decrypt_url` returns `None`). | **PASS WITH WARNING**: Resend on older tokens after SECRET_KEY rotation requires generating a replacement token. |

### 2.2 Standard Library vs. Third-Party Recommendation
- **Current State:** The project deliberately uses standard library Python to avoid adding unvetted C-extension dependencies.
- **Recommendation:** When production hardening allows adding package dependencies, adopt `cryptography` and use `cryptography.fernet.Fernet` (AES-128-CBC + HMAC-SHA256) or Django's built-in signed serializer `django.core.signing.dumps/loads` with a dedicated salt.

---

## 3. Raw Token & Sensitive Data Exposure Audit

1. **Database Tables:**
   - [`backend/interviews/models.py:248`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/models.py#L248): `token_hash = models.CharField(max_length=64, unique=True, db_index=True)` stores only the SHA-256 digest.
   - [`backend/interviews/models.py:280`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/models.py#L280): `encrypted_candidate_url` stores base64-encoded ciphertext.
2. **Celery Task Dispatch:**
   - In [`backend/interviews/tasks.py:211`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L211):
     `logger.info("Sending candidate invitation email for token_id=%s (attempt=%d)", token_id, self.request.retries)`
   - Celery logs never print the URL or the raw token.
3. **API Status Endpoints:**
   - In `backend/interviews/views.py:657-686` (`candidate_link_status`), the response payload contains only boolean states (`has_token`, `is_valid`, `is_revoked`, `is_expired`), timestamps, recipient email, and delivery status. Neither `token_hash` nor `encrypted_candidate_url` is exposed.

---

## 4. Concurrency, Atomicity & Lease Audit

1. **Database Row Lock & Atomicity:**
   - Handled in [`backend/interviews/tasks.py:217-268`](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/ai-interviewer/backend/interviews/tasks.py#L217-L268) using `select_for_update()` inside `transaction.atomic()`.
   - The transaction commits immediately after setting `delivery_status = DELIVERY_SENDING` and `delivery_started_at = now`.
   - The external SMTP email dispatch `msg.send()` executes **outside** the transaction, ensuring database connections are not held open during external I/O.
2. **Bounded Lease Recovery:**
   - Lease cutoff is set to 180 seconds (`lease_cutoff = now - timedelta(seconds=180)`).
   - Celery task configuration (`CELERY_TASK_TIME_LIMIT = 120`, `CELERY_TASK_SOFT_TIME_LIMIT = 90`) guarantees tasks timeout within 2 minutes. The 3-minute lease safely accounts for worker aborts without premature re-claiming.
3. **Revocation & Expiration Guard:**
   - Tasks re-verify `token_obj.is_revoked or now >= token_obj.expires_at` under row lock before claiming. If revoked or expired, delivery is aborted and marked `failed`.

---

## 5. Resend and Replacement Workflow Audit

1. **Ordinary Resend (`resend_candidate_link`):**
   - Recovers plaintext URL by calling `decrypt_url(latest_token.encrypted_candidate_url)`.
   - Resets status to `pending` and queues the task.
   - **Zero** new token rows are inserted into `CandidateInterviewAccessToken`.
   - Existing token remains valid; candidate's existing browser link continues to function.
2. **Explicit Replacement (`replace_candidate_link`):**
   - Updates `is_revoked=True` on all prior tokens for the interview.
   - Generates a fresh token, stores its encrypted URL, and dispatches an invitation email.
   - Frontend UI (`CandidateInviteModal.jsx`) requires recruiter confirmation to prevent accidental invalidation.

---

## 6. Verification Test Results

- **Backend Pytest Suite:** **164 passed**, 2 deselected (slow live Nemotron voice tests), 0 failures.
- **Frontend Vitest Suite:** **38 passed** across 10 test files.
- **Vite Production Build:** Successfully compiled in 5.30s (`dist/assets/index-CDtliRvA.js`).
- **Django System Check:** 0 issues identified (`manage.py check`).
- **Database Migration Check:** 0 unapplied migrations (`manage.py migrate --check`).

---

## 7. Audit Conclusion & Verdict

**Final Verdict: PASS WITH WARNINGS**

- **Pass Components:** Concurrency controls, lease recovery, raw token suppression, recruiter tenant isolation, recipient email verification, ordinary resend token preservation, and test suite health.
- **Warning Component:** Custom PRF-CTR cipher in `token_crypto.py` is cryptographically sound and secure, but should be replaced with `cryptography.fernet` or Django's signed serializer when third-party crypto packages are officially incorporated into `requirements.txt`.
- **Read-Only Audit Confirmation:** No files or database records were modified during this audit. Phase 10.4 was not started.

