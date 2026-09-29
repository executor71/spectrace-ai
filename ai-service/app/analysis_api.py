import logging
from threading import BoundedSemaphore
from fastapi import APIRouter, Depends, HTTPException
from app.analysis_models import AnalysisRequest, AnalysisResult
from app.analysis_service import AnalysisInputError, AnalysisService, InvalidAnalysisError
from app.llm_provider import LocalLlmProvider, LlmUnavailableError
from app.local_embedding import EmbeddingInputTooLongError
from app.search_api import get_search

router = APIRouter()
LOG = logging.getLogger(__name__)
slot = BoundedSemaphore(1)


def get_analysis_service():
    return AnalysisService(get_search(), LocalLlmProvider())


@router.post('/internal/v1/requirement-analysis', response_model=AnalysisResult)
def analyze(request: AnalysisRequest, service=Depends(get_analysis_service)):
    if not slot.acquire(blocking=False):
        raise HTTPException(429, detail={'code': 'ANALYSIS_BUSY', 'message': 'An analysis is already running'})
    try:
        return service.analyze(request)
    except (AnalysisInputError, EmbeddingInputTooLongError) as error:
        raise HTTPException(422, detail={'code':'ANALYSIS_INPUT_TOO_LONG','message':'Input must fit the unchanged vector search limits (2000 characters and 512 tokens)'}) from error
    except InvalidAnalysisError as error:
        raise HTTPException(502, detail={'code':'INVALID_ANALYSIS_OUTPUT','message':'Model output failed schema or grounding validation'}) from error
    except LlmUnavailableError as error:
        raise HTTPException(503, detail={'code':'ANALYSIS_MODEL_UNAVAILABLE','message':'Local analysis model is unavailable or timed out'}) from error
    except Exception as error:
        LOG.exception('Requirement analysis failed')
        raise HTTPException(503, detail={'code':'ANALYSIS_UNAVAILABLE','message':'Analysis or evidence search is unavailable'}) from error
    finally:
        slot.release()
