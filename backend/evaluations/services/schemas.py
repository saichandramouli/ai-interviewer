import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class CompetencyEvaluationItem(BaseModel):
    competency: str = Field(..., description="Name of the evaluated competency or technical skill.")
    score: float = Field(..., ge=0.0, le=100.0, description="Numerical score between 0 and 100.")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Relative weight of this competency.")
    strengths: List[str] = Field(default_factory=list, description="Specific observed strengths for this competency.")
    improvement_areas: List[str] = Field(default_factory=list, description="Specific observed gaps or improvement areas.")
    evidence_sufficient: bool = Field(default=True, description="Whether sufficient candidate answer evidence was present.")


class QuestionEvaluationItem(BaseModel):
    question_id: Optional[int] = Field(default=None, description="Actual ID of the approved question.")
    sequence_number: Optional[int] = Field(default=None, description="Sequence number of the question.")
    question_text: str = Field(default="", description="Question that was presented.")
    score: float = Field(..., ge=0.0, le=100.0, description="Score between 0 and 100 for this answer.")
    observation: str = Field(..., description="Objective observation of what the candidate answered.")
    evidence_sufficient: bool = Field(default=True, description="Whether the answer provided sufficient evidence.")


class EvaluationOutputSchema(BaseModel):
    overall_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Aggregated score between 0 and 100.")
    competency_scores: Dict[str, float] = Field(default_factory=dict, description="Dictionary mapping competency name to score (0-100).")
    competency_details: List[CompetencyEvaluationItem] = Field(default_factory=list, description="Detailed breakdown per competency.")
    strengths: List[str] = Field(default_factory=list, description="Key overall demonstrated strengths (supported by evidence).")
    improvement_areas: List[str] = Field(default_factory=list, description="Key overall gaps or improvement areas.")
    evidence_summary: str = Field(..., description="Objective, evidence-based synthesis of interview performance.")
    question_evaluations: List[QuestionEvaluationItem] = Field(default_factory=list, description="Breakdown of individual questions.")
    evaluation_completeness: str = Field(default="complete", description="'complete', 'partial', or 'insufficient_data'.")
    missing_evidence: List[str] = Field(default_factory=list, description="Competencies or questions lacking sufficient evidence.")

    @field_validator('overall_score')
    @classmethod
    def validate_overall_score(cls, v):
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("overall_score must be between 0 and 100.")
        return v

