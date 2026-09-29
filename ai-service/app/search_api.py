import logging

from fastapi import APIRouter, Depends, HTTPException
from app.db import rag_connection_settings
from app.local_embedding import EmbeddingInputTooLongError, get_embedding_provider
from app.vector_search import CorpusNotReadyError, SearchHit, SearchRequest, VectorSearch

LOG = logging.getLogger(__name__)
router = APIRouter()


def get_search() -> VectorSearch:
    return VectorSearch(get_embedding_provider(), rag_connection_settings())


@router.post('/internal/v1/search', response_model=list[SearchHit])
def search(request: SearchRequest, engine: VectorSearch = Depends(get_search)):
    try:
        return engine.search(request)
    except EmbeddingInputTooLongError as error:
        raise HTTPException(status_code=422, detail={'code':'QUERY_TOO_LONG','message':str(error)}) from error
    except CorpusNotReadyError as error:
        raise HTTPException(status_code=503, detail={'code':'CORPUS_NOT_READY','message':'Embedding profile or corpus is not ready'}) from error
    except Exception as error:
        LOG.exception('Vector search failed')
        raise HTTPException(status_code=503, detail={'code':'SEARCH_UNAVAILABLE','message':'Search is temporarily unavailable'}) from error
