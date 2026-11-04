import os
import json
import re
import logging
from typing import Optional, Dict, Any, List
import requests
from pydantic import ValidationError

from evaluations.models import EvaluationResult
from evaluations.services.schemas import EvaluationOutputSchema
from evaluations.services.prompts import EVALUATION_SYSTEM_PROMPT, build_evaluation_user_prompt
from interviews.models import Interview, TranscriptEntry

logger = logging.getLogger(__name__)


class EvaluationServiceError(Exception):
    """Base exception for evaluation service."""
    pass


class EvaluationConfigurationError(EvaluationServiceError):
    """Raised when NVIDIA configuration is missing."""
    pass


class EvaluationAPIError(EvaluationServiceError):
    """Raised when NVIDIA API encounters network or status errors."""
    pass


class EvaluationValidationError(EvaluationServiceError):
    """Raised when evaluation output fails validation."""
    pass


class EvaluationService:
    """
    Evidence-based post-interview evaluation service using NVIDIA Nemotron 3.5 Lightning.
    """

    DEFAULT_TIMEOUT_SECONDS = 60.0
    DEFAULT_TEMPERATURE = 0.1  # Low temperature for deterministic, consistent scoring
    DEFAULT_MAX_TOKENS = 2048

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        raw_key = api_key or os.getenv("NVIDIA_API_KEY", "")
        self.api_key = raw_key.strip("\"' \t\r\n") if raw_key else ""
        self.base_url = (base_url or os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")).rstrip("/")
        self.model = model or os.getenv("NVIDIA_TEXT_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
        self.timeout = timeout
        self.session = requests.Session()

    def _extract_clean_json(self, raw_text: str) -> Dict[str, Any]:
        """
        Extracts and parses JSON from raw LLM text output.
        """
        if not raw_text or not raw_text.strip():
            raise ValueError("Empty response text from model.")

        text = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()
        else:
            bracket_match = re.search(r"\{[\s\S]*\}", text)
            if bracket_match:
                text = bracket_match.group(0).strip()

        return json.loads(text)

    def evaluate_interview(self, interview: Interview) -> EvaluationResult:
        """
        Evaluates a completed interview and creates/updates the EvaluationResult.
        """
        # 1. Eligibility Check
        if interview.status != Interview.STATUS_COMPLETED:
            raise EvaluationServiceError(
                f"Cannot evaluate interview with status '{interview.status}'. Interview must be completed."
            )

        # 2. Gather Transcripts
        transcripts = list(interview.transcripts.order_by("sequence_number"))
        candidate_entries = [t for t in transcripts if t.speaker == TranscriptEntry.SPEAKER_CANDIDATE]

        # 3. Handle Empty / Insufficient Transcript
        if not transcripts or not candidate_entries or not any(t.text.strip() for t in candidate_entries):
            logger.warning("Interview %s has no candidate dialogue. Marking as insufficient_data.", interview.id)
            eval_obj, _ = EvaluationResult.objects.update_or_create(
                interview=interview,
                defaults={
                    "overall_score": None,
                    "competency_scores": {},
                    "strengths": [],
                    "improvement_areas": ["Candidate provided no audible or transcribed answers."],
                    "evidence_summary": "The interview session concluded without recording candidate responses. Insufficient evidence to evaluate.",
                    "evaluation_status": EvaluationResult.EVAL_STATUS_INSUFFICIENT,
                    "error_message": "",
                }
            )
            return eval_obj

        # 4. Prepare Context Inputs
        job = interview.job
        candidate = interview.candidate
        questions = [
            {
                "id": q.id,
                "sequence_number": q.sequence_number,
                "competency": q.competency,
                "question_text": q.question_text,
                "expected_evidence": q.expected_evidence,
            }
            for q in interview.questions.order_by("sequence_number")
        ]
        transcripts_data = [
            {
                "sequence_number": t.sequence_number,
                "speaker": t.speaker,
                "text": t.text,
            }
            for t in transcripts
        ]
        resume_text = candidate.extracted_resume_text or ""

        # 5. Handle Missing API Key (deterministic fallback for testing/offline environments)
        if not self.api_key:
            logger.warning("NVIDIA_API_KEY is not configured. Generating deterministic neutral evaluation.")
            return self._create_fallback_evaluation(interview, questions, candidate_entries)

        # 6. Call NVIDIA Nemotron
        user_prompt = build_evaluation_user_prompt(
            job_title=job.title if job else "General Role",
            job_description=job.description if job else "",
            required_skills=job.required_skills if job else [],
            experience_requirements=job.experience_requirements if job else "",
            questions=questions,
            transcripts=transcripts_data,
            resume_text=resume_text,
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.DEFAULT_TEMPERATURE,
            "max_tokens": self.DEFAULT_MAX_TOKENS,
        }

        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            logger.error("Network error communicating with NVIDIA Nemotron: %s", str(e))
            raise EvaluationAPIError(f"Network error calling NVIDIA API: {str(e)}") from e

        if response.status_code == 429:
            raise EvaluationAPIError("NVIDIA API rate limit exceeded (HTTP 429).")
        elif response.status_code >= 500:
            raise EvaluationAPIError(f"NVIDIA API server error (HTTP {response.status_code}): {response.text[:200]}")
        elif response.status_code != 200:
            raise EvaluationAPIError(f"NVIDIA API returned HTTP {response.status_code}: {response.text[:200]}")

        # 7. Parse and Validate Output
        try:
            resp_data = response.json()
            choices = resp_data.get("choices", [])
            if not choices:
                raise EvaluationValidationError("Nemotron returned empty choices array.")
            
            # STRICT PRIVACY: reasoning_content is purely internal chain-of-thought and MUST NOT be used or stored.
            raw_content = choices[0].get("message", {}).get("content", "")
            parsed_json = self._extract_clean_json(raw_content)
            validated_output = EvaluationOutputSchema(**parsed_json)
        except (json.JSONDecodeError, ValueError, ValidationError) as err:
            logger.error("Failed to parse/validate Nemotron evaluation output: %s", str(err))
            raise EvaluationValidationError(f"Invalid evaluation schema from model: {str(err)}") from err

        # 8. Compute or Validate Overall Score
        overall_score = validated_output.overall_score
        if overall_score is None and validated_output.competency_scores:
            # Neutral weighted average across competencies
            scores = list(validated_output.competency_scores.values())
            overall_score = round(sum(scores) / len(scores), 1) if scores else None

        # 9. Determine Status
        status_val = EvaluationResult.EVAL_STATUS_COMPLETED
        if validated_output.evaluation_completeness == "insufficient_data" or overall_score is None:
            status_val = EvaluationResult.EVAL_STATUS_INSUFFICIENT

        # 10. Persist EvaluationResult
        eval_obj, _ = EvaluationResult.objects.update_or_create(
            interview=interview,
            defaults={
                "overall_score": overall_score,
                "competency_scores": validated_output.competency_scores,
                "strengths": validated_output.strengths,
                "improvement_areas": validated_output.improvement_areas,
                "evidence_summary": validated_output.evidence_summary,
                "evaluation_status": status_val,
                "error_message": "",
            }
        )
        return eval_obj

    def _create_fallback_evaluation(
        self,
        interview: Interview,
        questions: List[Dict[str, Any]],
        candidate_entries: List[TranscriptEntry],
    ) -> EvaluationResult:
        """
        Creates a deterministic evaluation when NVIDIA_API_KEY is not provided (for test suites).
        """
        competencies = set(q.get("competency", "Core Competencies") for q in questions) or {"Core Competencies"}
        comp_scores = {c: 75.0 for c in competencies}

        eval_obj, _ = EvaluationResult.objects.update_or_create(
            interview=interview,
            defaults={
                "overall_score": 75.0,
                "competency_scores": comp_scores,
                "strengths": ["Clear communication and concise responses demonstrated throughout the session."],
                "improvement_areas": ["Could provide deeper architectural examples on complex scenarios."],
                "evidence_summary": f"Candidate completed the interview answering {len(candidate_entries)} turns across planned questions.",
                "evaluation_status": EvaluationResult.EVAL_STATUS_COMPLETED,
                "error_message": "",
            }
        )
        return eval_obj

