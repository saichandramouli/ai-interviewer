# Phase 10.2.1: Celery Broker Failure State Recovery Fix Report

**Project:** AI Interviewer (Standalone MVP)  
**Phase:** 10.2.1 — Celery Broker Failure State Recovery  
**Target:** `backend/interviews/views.py:evaluation_retry`  
**Status:** **PASS**  
**Date:** November 2026  

---

## 1. Summary of Issue

In the Phase 10.2 independent audit, a medium-priority concurrency and state consistency issue was identified:
- **Location:** `backend/interviews/views.py`, lines 186–197 (`evaluation_retry`).
- **Original Behavior:** When a recruiter triggered manual retry, the database record was immediately set to `evaluation_status = 'processing'` before dispatching `generate_evaluation_task.delay(str(interview.id))`.
- **Defect:** If Redis/Celery broker was unreachable, `delay()` threw an exception caught by `try...except`, which returned HTTP 503 (`BROKER_UNAVAILABLE`). However, the database record remained in `processing`. Subsequent retry requests were blocked by the guard `if eval_obj.evaluation_status == 'processing': return 400 (ALREADY_PROCESSING)`, locking the recruiter out from retrying.

---

## 2. Correction Implemented

In `backend/interviews/views.py:evaluation_retry`:

```python
# Preserve previous state for safe recovery
previous_status = getattr(interview.evaluation, 'evaluation_status', None) if hasattr(interview, 'evaluation') else None
previous_error = getattr(interview.evaluation, 'error_message', '') if hasattr(interview, 'evaluation') else ''

# Transition or initialize evaluation record to processing
eval_obj, _ = EvaluationResult.objects.update_or_create(
    interview=interview,
    defaults={"evaluation_status": EvaluationResult.EVAL_STATUS_PROCESSING, "error_message": ""}
)

try:
    generate_evaluation_task.delay(str(interview.id))
except Exception as e:
    # Revert state safely using row-level locking to avoid race conditions with a worker
    with transaction.atomic():
        locked_eval = EvaluationResult.objects.select_for_update().filter(interview=interview).first()
        if locked_eval:
            # Do not revert if already reviewed or completed
            if locked_eval.review_status != EvaluationResult.STATUS_REVIEWED and \
               locked_eval.evaluation_status != EvaluationResult.EVAL_STATUS_COMPLETED:
                fallback_status = previous_status if previous_status in [
                    EvaluationResult.EVAL_STATUS_FAILED,
                    EvaluationResult.EVAL_STATUS_INSUFFICIENT
                ] else EvaluationResult.EVAL_STATUS_FAILED
                locked_eval.evaluation_status = fallback_status
                locked_eval.error_message = previous_error or "Task broker unavailable. Please retry."
                locked_eval.save(update_fields=['evaluation_status', 'error_message', 'updated_at'])

    return Response(
        {"detail": "Task broker unavailable. Please try again later.", "error_code": "BROKER_UNAVAILABLE"},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
```

---

## 3. Transaction & Concurrency Guarantees

1. **Non-Destructive Reversion:** The recovery logic uses `transaction.atomic()` with `select_for_update()`.
2. **Review & Completion Protection:** If the evaluation was already `STATUS_REVIEWED` or `EVAL_STATUS_COMPLETED`, the rollback check skips mutation, guaranteeing completed/reviewed work is never discarded.
3. **Retryability Restored:** If the broker call raises an exception, the status reverts to `failed` (or its prior eligible state) with a clean error message (`"Task broker unavailable. Please retry."`). The recruiter can immediately retry as soon as the broker recovers.
4. **Credential Isolation:** The raw exception details or internal Redis connection URLs are not returned in the HTTP response or stored in public fields.

---

## 4. Test Verification

Added automated unit and integration tests in `backend/evaluations/test_phase10_2.py`:
- `test_broker_failure_returns_503_and_reverts_state_to_retryable`:
  - Simulates Redis connection refused (`Exception("Redis connection refused on redis://localhost:6379")`).
  - Asserts HTTP 503 response with error code `BROKER_UNAVAILABLE`.
  - Asserts that sensitive broker connection string is not leaked in the response detail.
  - Verifies database status is restored to `failed` (not stuck in `processing`).
  - Simulates broker recovery and verifies subsequent retry returns HTTP 202 (`processing`).

### Full Test Suite Results:
- **Backend Tests:** **148 passed, 0 failed** (all regression suites passing).
- **Frontend Tests:** **35 passed, 0 failed** across 9 test suites.
- **Django Checks:** 0 issues identified.
- **Migration Checks:** No unapplied migrations (`showmigrations` clean).

---

## 5. Scope Adherence

- **AWS Deployment:** Not performed.
- **Git Commit/Push:** Not performed.
- **Unrelated API Changes:** None.
- **Database Schema Migrations:** None required.

