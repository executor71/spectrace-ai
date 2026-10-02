from functools import lru_cache
from threading import Lock
from typing import Literal
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,ConfigDict,Field,field_validator
from app.local_embedding import EmbeddingInputTooLongError
from retrieval.core import SearchEngine,RerankerUnavailable,settings
from retrieval.reranker import LocalRerankerProvider

app=FastAPI(title='Phase 8 isolated retrieval experiment');serial=Lock()
class Request(BaseModel):
    model_config=ConfigDict(extra='forbid')
    queryId:str=Field(min_length=1,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
    queryText:str=Field(min_length=1,max_length=2000)
    strategy:Literal['VECTOR','LEXICAL','HYBRID','HYBRID_RERANK']
    @field_validator('queryText',mode='before')
    @classmethod
    def trim(cls,value):return value.strip() if isinstance(value,str) else value
@lru_cache(maxsize=1)
def engine():
    cfg=settings();return SearchEngine(cfg,LocalRerankerProvider(cfg['reranker']))
@app.get('/health')
def health():return {'status':'UP'}
@app.post('/internal/v1/retrieval')
def search(request:Request):
    with serial:
        try:return engine().search(request.queryId,request.queryText,request.strategy)
        except RerankerUnavailable as e:raise HTTPException(503,detail={'code':'RERANKER_UNAVAILABLE','fallback':None}) from e
        except EmbeddingInputTooLongError as e:raise HTTPException(422,detail={'code':'QUERY_TOO_LONG'}) from e
        except Exception as e:raise HTTPException(503,detail={'code':'RETRIEVAL_UNAVAILABLE','fallback':None}) from e
