"""Public analysis contract. Facts are extractive, never free-form LLM claims."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

Text = Annotated[str, Field(strict=True, min_length=1, max_length=2000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class AnalysisRequest(StrictModel):
    requirementId: str
    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(min_length=1, max_length=10000)]


class GroundedCondition(StrictModel):
    text: Text
    chunkId: str


class GroundedApi(StrictModel):
    api: Text
    chunkId: str


class Evidence(StrictModel):
    documentId: str
    chunkId: str
    documentType: str
    section: str
    contentSnippet: str
    score: Annotated[float, Field(allow_inf_nan=False, ge=-1.001, le=1.001)]


class AnalysisResult(StrictModel):
    requirementId: str
    confirmedConditions: list[GroundedCondition]
    ambiguousExpressions: list[Text]
    missingConditions: list[Text]
    relatedBusinessRules: list[GroundedCondition]
    relatedApis: list[GroundedApi]
    clarificationQuestions: list[Text]
    evidence: list[Evidence]


class AnalysisDraft(StrictModel):
    # LLM selects trusted catalog IDs. It cannot author facts, APIs, or evidence.
    evidenceSufficiency: Literal["SUFFICIENT", "PARTIAL", "NONE"]
    confirmedConditionIds: Annotated[list[Text], Field(max_length=4)]
    ambiguousExpressions: Annotated[list[Text], Field(max_length=12)]
    missingConditions: Annotated[list[Text], Field(max_length=12)]
    relatedBusinessRuleIds: Annotated[list[Text], Field(max_length=4)]
    relatedApiIds: Annotated[list[Text], Field(max_length=3)]
    clarificationQuestions: Annotated[list[Text], Field(max_length=12)]
