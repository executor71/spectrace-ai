import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from psycopg.types.json import Jsonb
from app.metrics import VERSION, digest, evaluate

app = FastAPI(title='Isolated Evaluation Service', docs_url=None, redoc_url=None, openapi_url=None)
ENGINE_HASH = hashlib.sha256(Path(__file__).with_name('metrics.py').read_bytes()).hexdigest()


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requirementId: UUID
    datasetVersion: Literal['phase6-v1'] = 'phase6-v1'
    contentMode: Literal['GENERATED','REVIEWED'] = 'GENERATED'


@app.exception_handler(RequestValidationError)
def invalid_request(request, error):
    return JSONResponse(status_code=400, content={'code':'INVALID_EVALUATION_INPUT','message':'UUID, datasetVersion, contentMode 및 허용 필드를 확인해 주세요.'})


def connection():
    # The application/generator never receives these credentials.
    return psycopg.connect(host=os.getenv('EVALUATION_DB_HOST','postgres'), dbname=os.getenv('EVALUATION_DB_NAME','legacy_assistant'),
                          user=os.getenv('EVALUATION_DB_USER','evaluation_reader'), password=os.environ['EVALUATION_DB_PASSWORD'],
                          options='-c search_path=evaluation -c statement_timeout=10000', connect_timeout=5)


def backend(path, allow_missing=False):
    try:
        response = httpx.get(os.getenv('BACKEND_URL','http://backend:8080') + path, timeout=15)
        if response.status_code == 404:
            if allow_missing: return None
            raise HTTPException(404, 'Requirement not found')
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise HTTPException(503, 'Requirement snapshot unavailable') from error


def search(query):
    try:
        # Only the public requirement text leaves this process. No Ground Truth labels or expected IDs.
        response = httpx.post(os.getenv('SEARCH_URL','http://ai-service:8000') + '/internal/v1/search', json={'query':query,'topK':5}, timeout=60)
        response.raise_for_status()
        hits = response.json()
        if not isinstance(hits,list) or len(hits)>5 or any(not isinstance(h,dict) or not all(k in h for k in ['documentId','chunkId','score']) for h in hits):
            raise ValueError('Invalid retrieval response')
        return hits
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(503,'Retrieval unavailable; no score fabricated') from error


def load_truth(requirement_id, version):
    with connection() as db:
        row = db.execute('SELECT g.truth_json,g.truth_hash,g.case_id,g.split,g.requirement_hash FROM evaluation.ground_truth g JOIN evaluation.requirement_binding b USING(dataset_version,case_id) WHERE b.requirement_id=%s AND g.dataset_version=%s', (requirement_id,version)).fetchone()
        if row is None: raise HTTPException(409,'Requirement is not bound to a frozen evaluation dataset')
        catalog = db.execute('SELECT entry FROM evaluation.evidence_catalog ORDER BY chunk_id').fetchall()
    truth, truth_hash, case_id, split, requirement_hash = row
    if digest(truth) != truth_hash: raise HTTPException(503,'Ground Truth integrity check failed')
    return truth, {'datasetVersion':version,'caseId':case_id,'split':split,'groundTruthHash':truth_hash,'requirementHash':requirement_hash}, [r[0] for r in catalog]


def save(report, snapshot):
    with connection() as db:
        db.execute('SELECT evaluation.record_run(%s,%s,%s,%s,%s)', (UUID(report['id']),UUID(report['requirementId']),report['dataset']['datasetVersion'],Jsonb(report),Jsonb(snapshot)))


@app.get('/health')
def health():
    with connection() as db: db.execute('SELECT count(*) FROM evaluation.ground_truth').fetchone()
    return {'status':'UP','metricVersion':VERSION}


@app.post('/api/evaluations', status_code=201)
def create_evaluation(request: EvaluationRequest):
    requirement_id = str(request.requirementId)
    requirement = backend('/api/requirements/' + requirement_id)
    truth, dataset, catalog = load_truth(request.requirementId, request.datasetVersion)
    public_requirement = {k:requirement[k] for k in ['title','description']}
    if digest(public_requirement) != dataset['requirementHash']:
        raise HTTPException(409,'Requirement does not match the frozen dataset input')
    report = {'id':str(uuid4()),'requirementId':requirement_id,'createdAt':datetime.now(timezone.utc).isoformat(),
              'dataset':dataset,'metricVersion':VERSION,'engineHash':ENGINE_HASH,'contentMode':request.contentMode,
              'status':'COMPLETED','metrics':None,'issues':[]}
    snapshot = {'groundTruth':truth,'requirement':public_requirement}
    try:
        batch = backend('/api/requirements/' + requirement_id + '/test-cases', allow_missing=True)
        if batch is None:
            source = backend('/api/requirements/' + requirement_id + '/analysis', allow_missing=True) or {}
            batch = {'testCases':[], 'sourceAnalysis':source,'generationId':None,'stale':False}
            report['issues'].append('NO_SAVED_GENERATION')
        if batch.get('stale'): report['issues'].append('STALE_GENERATION_SNAPSHOT')
        query = requirement['title'] + '\n' + requirement['description']
        inputs = {'requirementId':requirement_id,'query':query,'testCases':[c['generatedContent'] if request.contentMode=='GENERATED' else {k:v for k,v in c.items() if k not in ['generatedContent','reviewedContent']} for c in batch['testCases']],
                  'sourceAnalysis':batch['sourceAnalysis'],'evidenceCatalog':catalog,'generationId':batch['generationId'],
                  'reviewRevisions':{c['testCaseId']:c['reviewRevision'] for c in batch['testCases']},'stale':batch['stale']}
        snapshot['inputs'] = inputs
        inputs['searchHits'] = search(query)
        # Persist the exact captured input. A concurrent review/generation does not mutate this run.
        report['metrics'] = evaluate(truth, inputs)
        report['inputHash'] = digest(inputs)
        report['generationId'] = inputs['generationId']
        report['retrievalSnapshot'] = {'query':query,'hits':inputs['searchHits'],'topK':5,'source':'unchanged-phase2-vector-baseline','corpusHash':digest(catalog)}
    except HTTPException as error:
        report['status'] = 'FAILED'
        report['issues'].append({'code':'INPUT_UNAVAILABLE','message':str(error.detail)})
    save(report,snapshot)
    return report


@app.get('/api/evaluations/{evaluation_id}')
def get_evaluation(evaluation_id: UUID):
    with connection() as db:
        row = db.execute('SELECT result_json FROM evaluation.evaluation_run WHERE id=%s',(evaluation_id,)).fetchone()
    if row is None: raise HTTPException(404,'Evaluation not found')
    return row[0]


@app.get('/api/requirements/{requirement_id}/evaluations')
def list_evaluations(requirement_id: UUID):
    backend('/api/requirements/' + str(requirement_id))
    with connection() as db:
        rows = db.execute('SELECT result_json FROM evaluation.evaluation_run WHERE requirement_id=%s ORDER BY created_at DESC,id DESC',(requirement_id,)).fetchall()
    return [r[0] for r in rows]

if os.getenv('APP_OTEL_ENABLED') == 'true':
    from workflow_otel.install import evaluation
    evaluation(app)
