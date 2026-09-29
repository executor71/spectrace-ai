from threading import BoundedSemaphore
from fastapi import APIRouter, Depends, HTTPException
from app.llm_provider import LocalLlmProvider, LlmUnavailableError
from app.test_case_models import GenerationRequest, GenerationResult
from app.test_case_service import TestCaseGenerator, InvalidTestCasesError

router = APIRouter()
slot = BoundedSemaphore(1)


def get_generator():
    return TestCaseGenerator(LocalLlmProvider())


@router.post('/internal/v1/test-cases/generate', response_model=GenerationResult)
def generate(request: GenerationRequest, service=Depends(get_generator)):
    if not slot.acquire(blocking=False):
        raise HTTPException(429, detail={'code': 'TEST_CASE_BUSY'})
    try:
        return service.generate(request)
    except InvalidTestCasesError as error:
        raise HTTPException(502, detail={'code': 'INVALID_TEST_CASE_OUTPUT'}) from error
    except ValueError as error:
        raise HTTPException(422, detail={'code': 'INVALID_ANALYSIS_SNAPSHOT'}) from error
    except LlmUnavailableError as error:
        raise HTTPException(503, detail={'code': 'TEST_CASE_MODEL_UNAVAILABLE'}) from error
    finally:
        slot.release()
