"""Phase 4 contract. Evidence references always resolve to the input snapshot."""
from typing import Annotated, Literal
from pydantic import Field
from app.analysis_models import StrictModel, AnalysisResult, Text

TestType = Literal['NORMAL', 'EXCEPTION', 'AUTHORIZATION', 'BOUNDARY', 'BUSINESS_RULE']


class EvidenceRef(StrictModel):
    documentId: str
    chunkId: str


class ExpectedResult(StrictModel):
    description: Text
    assertions: list[dict]


class TestCase(StrictModel):
    testCaseId: str
    requirementId: str
    type: TestType
    scenario: Text
    preconditions: list[Text]
    input: dict
    steps: list[Text]
    expectedResult: ExpectedResult
    evidence: list[EvidenceRef]
    executable: bool


class GenerationRequest(StrictModel):
    requirementId: str
    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(min_length=1, max_length=10000)]
    analysis: AnalysisResult


class GenerationResult(StrictModel):
    testCases: list[TestCase]
    clarificationRequired: list[str]
    uncoveredTypes: list[TestType]
    policyHash: str
    llmCalls: Annotated[int, Field(ge=0, le=2)]


class Selection(StrictModel):
    candidateIds: Annotated[list[str], Field(max_length=30)]
