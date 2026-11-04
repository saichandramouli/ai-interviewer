# Phase 10.1: Repository Audit & Architecture Inspection Report

**Date:** November 2026  
**Module:** `backend/evaluations` & `backend/interviews`  
**Purpose:** Pre-implementation architectural analysis for Phase 10.1 (Automated AI Evaluation Engine).

---

## 1. Existing Evaluation Architecture

### A. Model Schema (`backend/evaluations/models.py`)
- **Model:** `EvaluationResult`
  - `id`: `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`
  - `interview`: `OneToOneField(Interview, on_delete=models.CASCADE, related_name='evaluation')` -> **Strictly enforces exactly one evaluation per interview.**
  - `overall_score`: `FloatField(null=True, blank=True)` with clean validator `0.0 <= overall_score <= 100.0`.
  - `competency_scores`: `JSONField(default=dict, blank=True)` with type check `isinstance(dict)`.
  - `strengths`: `JSONField(default=list, blank=True)` with type check `isinstance(list)`.
  - `improvement_areas`: `JSONField(default=list, blank=True)` with type check `isinstance(list)`.
  - `evidence_summary`: `TextField(blank=True, default='')`.
  - `review_status`: `CharField(max_length=20, choices=[('pending', 'Pending Review'), ('reviewed', 'Reviewed')], default='pending', db_index=True)`.
  - `created_at`, `updated_at`: `DateTimeField(auto_now_add/auto_now)`.
- **Schema Assessment:**
  - `EvaluationResult` has a flexible `JSONField` for `competency_scores`, `strengths`, and `improvement_areas`.
  - To support execution lifecycle states (`pending`, `processing`, `completed`, `failed`, `insufficient_data`) alongside recruiter `review_status` without breaking existing serializers, we can either:
    - Extend `EvaluationResult` with `evaluation_status` (choices: `pending`, `processing`, `completed`, `failed`, `insufficient_data`) and `error_message` via a backward-compatible migration, OR
    - Use `EvaluationResult` for the generated result and record status in the `InterviewViewSet.evaluation` response, or add clean status fields.
    - Adding `evaluation_status` (`default='pending'`) and `error_message` (`TextField(blank=True, default='')`) to `EvaluationResult` is clean, non-destructive, and gives first-class observability.

### B. Serializers & Views (`backend/evaluations/`)
- `serializers.py`: `EvaluationResultSerializer` serializes `id`, `interview`, `overall_score`, `competency_scores`, `strengths`, `improvement_areas`, `evidence_summary`, `review_status`, `created_at`, `updated_at`.
- `views.py`: Currently an empty stub (`# Create your views here.`).
- `interviews/views.py`: Exposes `@action(detail=True, methods=['get'], url_path='evaluation')` on `InterviewViewSet`. It checks `hasattr(interview, 'evaluation')` and returns 404 if not found.
- Recruiter isolation: `InterviewViewSet` scopes all queries by `created_by=request.user`. Thus, only the owning recruiter can query `/api/v1/interviews/{id}/evaluation/`.

---

## 2. Interview Completion Lifecycle

### A. Completion Paths
1. **Planned Completion:**
   - In `InterviewOrchestrationService.advance_question()`, after the last question is asked and answered (or when `conclude_interview()` is triggered):
     ```python
     return self.conclude_interview(reason="All planned interview questions answered.")
     ```
2. **Time Limit Expiration:**
   - In `InterviewOrchestrationService.advance_question()`, if `elapsed >= duration_limit`:
     ```python
     return self.conclude_interview(reason="Time limit expired.")
     ```
3. **Explicit Candidate Finish:**
   - Candidate finish can be dispatched to `conclude_interview()` or a dedicated `CandidateFinishInterviewView`.

### B. Canonical Completion Point: `InterviewOrchestrationService.conclude_interview()`
- Transitions `interview.status = Interview.STATUS_COMPLETED`.
- Saves `ended_at = timezone.now()`.
- Delivers optional closing statement to `TranscriptEntry`.
- Records `session_completed` in `InterviewEvent`.
- **Key Observation:** Because `conclude_interview` is decorated with `@transaction.atomic`, dispatching the evaluation task using:
  ```python
  from evaluations.tasks import generate_evaluation_task
  transaction.on_commit(lambda: generate_evaluation_task.delay(str(self.interview.id)))
  ```
  guarantees that:
  - The task is dispatched **only after** the transaction commits.
  - The task is **never** dispatched before DB commit or if the transaction rolls back.
  - Cancelled, failed, or draft interviews never call `conclude_interview`.

---

## 3. Existing NVIDIA Nemotron Integration

- **Implementation:** `backend/interviews/services/dialogue_service.py`
  - Model: `os.getenv("NVIDIA_TEXT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")`.
  - Base URL: `os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")`.
  - Auth: `Bearer <NVIDIA_API_KEY>` (strips quotation marks safely).
  - Endpoint: `{base_url}/chat/completions`.
  - Security: Strips `reasoning_content` immediately. Handles JSON extraction from markdown code fences or `{...}` blocks.
- **Reuse for Evaluation:**
  - We will implement `backend/evaluations/services/evaluation_service.py` that utilizes the same NVIDIA endpoint, model configuration, and error-handling conventions, but with a dedicated evidence-based post-interview evaluation prompt.

---

## 4. Existing Celery Architecture

- **Celery App:** `backend/config/celery.py` with `app.autodiscover_tasks()`.
- **Existing Task Pattern:** `backend/interviews/tasks.py` (`generate_plan_task`).
  - Uses `@shared_task(bind=True, max_retries=2, default_retry_delay=10, soft_time_limit=..., time_limit=...)`.
  - Bounded exponential backoff / retry on network and HTTP 429/5xx errors.
  - Rejects permanent failures without retry.
- **Evaluation Task:**
  - Will be defined in `backend/evaluations/tasks.py` as `generate_evaluation_task(interview_id: str)`.
  - Celery will autodiscover it under the `evaluations` app.

---

## 5. Recruiter Ownership & Security

- Recruiter tenant isolation is enforced at the DRF ViewSet layer (`created_by=request.user`).
- Anonymous users and public candidate tokens are barred from accessing evaluation results.
- `CandidateBaseView` only exposes `/api/v1/candidate/session/`, `/consent/`, `/start/`, `/submit-turn/`, and `/synthesize-speech/`. Evaluation data is never leaked via candidate endpoints.
- No personal data (phone, email, demographic characteristics) will be sent in the evaluation prompt.

---

## 6. Files to Create and Modify

| Action | Path | Description |
|---|---|---|
| **Create** | `backend/evaluations/services/evaluation_service.py` | Evidence-based evaluation logic, prompt formulation, Nemotron API call, Pydantic/dataclass schema validation, scoring calculation. |
| **Create** | `backend/evaluations/services/prompts.py` | System and user prompts for Nemotron evaluation with anti-injection guards. |
| **Create** | `backend/evaluations/tasks.py` | Celery task `generate_evaluation_task` with idempotency, concurrency lock, and retry policy. |
| **Modify** | `backend/evaluations/models.py` | Add `evaluation_status` (`pending`, `processing`, `completed`, `failed`, `insufficient_data`) and `error_message` to `EvaluationResult`. |
| **Create Migration** | `backend/evaluations/migrations/0002_add_status_and_error.py` | Add non-destructive fields to `EvaluationResult`. |
| **Modify** | `backend/evaluations/serializers.py` | Expose `evaluation_status` and `error_message`. |
| **Modify** | `backend/interviews/services/orchestrator.py` | Trigger evaluation dispatch via `transaction.on_commit` in `conclude_interview()`. |
| **Modify** | `backend/interviews/candidate_views.py` | Add optional candidate finish view / finish turn handling if needed. |
| **Modify** | `backend/interviews/views.py` | Update `evaluation` action to return evaluation status and detailed payload. |
| **Create** | `backend/evaluations/test_phase10_1.py` | Full test suite for service, prompts, Celery tasks, idempotency, edge cases, and API permissions. |
| **Create** | `docs/PHASE_10_1_IMPLEMENTATION_REPORT.md` | Final documentation and sign-off report. |

---

## 7. Migration & Compatibility Assessment

- Adding `evaluation_status` and `error_message` with default values to `EvaluationResult` is 100% backward-compatible with existing tests and seeded records.
- Existing tests expecting `overall_score`, `competency_scores`, `strengths`, `improvement_areas`, `evidence_summary` will continue to pass without change.

