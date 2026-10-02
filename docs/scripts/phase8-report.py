from pathlib import Path
import hashlib,json,statistics,urllib.request
root=Path(__file__).resolve().parents[2];dest=root/'docs/phase8-evidence'
def read(name):return json.loads((dest/name).read_text(encoding='utf-8'))
def write(name,value):(dest/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
freeze=read('dataset-freeze.json');dataset=read('evaluation-dataset.json');summary=read('comparison-summary.json');comparison=read('query-by-query-comparison.json');latency=read('latency-results.json')
assert hashlib.sha256((dest/'evaluation-dataset.json').read_bytes()).hexdigest()==freeze['datasetSha256']
assert hashlib.sha256((root/'evaluation-service/datasets/retrieval-v1.json').read_bytes()).hexdigest()==freeze['datasetSha256']
strategies=['VECTOR','LEXICAL','HYBRID','HYBRID_RERANK'];results={s:read(f) for s,f in zip(strategies,['vector-results.json','lexical-results.json','hybrid-results.json','reranker-results.json'])}
assert len(comparison)==32 and all(len(rows)==32 for rows in results.values())
assert all(len(samples)==96 for samples in latency['steadyStateSamples'].values())
assert all(r['corpusHash']==freeze['corpusHash'] for rows in results.values() for r in rows)
baseline=json.loads((root/'docs/phase2-evidence/top5-results.json').read_text(encoding='utf-8'))
legacy=[];legacy_metrics=[];weaknesses=[];corpus=read('corpus-snapshot.json');bykey={r['documentKey']:r['documentId'] for r in corpus['chunks']}
byid={r['chunkId']:r for r in corpus['chunks']}
for old in baseline:
    qid='phase2-'+str(old['number']);vector=next(r for r in results['VECTOR'] if r['queryId']==qid)
    assert [r['chunkId'] for r in vector['results']]==[r['chunkId'] for r in old['hits']]
    assert [r['vectorScore'] for r in vector['results']]==[r['score'] for r in old['hits']]
    # Start/end live Phase 2 API verification is independent of the experiment wrapper.
    request=urllib.request.Request('http://127.0.0.1:8000/internal/v1/search',data=json.dumps({'query':old['query'],'topK':5}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=90) as response:live=json.load(response)
    assert [r['chunkId'] for r in live]==[r['chunkId'] for r in old['hits']]
    assert [r['score'] for r in live]==[r['score'] for r in old['hits']]
    legacy.append({'queryId':qid,'queryText':old['query'],'expectedDocumentKeys':old['expectedDocumentKeys'],'originalTop5':old['hits'],'currentTop5':live,'rankIdentical':True,'scoreIdentical':True})
    expected_docs={bykey[key] for key in old['expectedDocumentKeys']};legacy_row={'queryId':qid,'expectedDocumentKeys':old['expectedDocumentKeys'],'strategies':{}}
    for strategy in strategies:
        top=next(r for r in results[strategy] if r['queryId']==qid)['results'];present={r['documentId'] for r in top};first=next((i for i,r in enumerate(top,1) if r['documentId'] in expected_docs),None)
        legacy_row['strategies'][strategy]={'hitAt5':int(bool(present&expected_docs)),'documentRecallAt5':len(present&expected_docs)/len(expected_docs),'mrrAt5':1/first if first else 0}
    legacy_metrics.append(legacy_row)
    found={r['documentId'] for r in old['hits']}
    for missing in [key for key in old['expectedDocumentKeys'] if bykey[key] not in found]:
        mappings={}
        hybrid=next(r for r in results['HYBRID'] if r['queryId']==qid)
        candidates={'VECTOR':hybrid['vectorCandidates'],'LEXICAL':next(r for r in results['LEXICAL'] if r['queryId']==qid)['candidates'],'HYBRID':hybrid['candidates'],'HYBRID_RERANK':next(r for r in results['HYBRID_RERANK'] if r['queryId']==qid)['candidates']}
        for strategy,rows in candidates.items():
            ranks=[i for i,r in enumerate(rows,1) if r['documentId']==bykey[missing]]
            mappings[strategy]={'bestChunkRankForDocument':min(ranks) if ranks else None,'inTop5':bool(ranks and min(ranks)<=5),'rankScope':'retrieved top-20 candidates; null means absent'}
        weaknesses.append({'queryId':qid,'queryText':old['query'],'missingDocumentKey':missing,'documentId':bykey[missing],'strategies':mappings})
write('baseline-end-regression.json',{'result':'PASS','queries':legacy})
write('phase2-weakness-comparison.json',weaknesses)
legacy_summary={s:{k:statistics.mean(r['strategies'][s][k] for r in legacy_metrics) for k in ['hitAt5','documentRecallAt5','mrrAt5']} for s in strategies}
write('phase2-legacy-document-comparison.json',{'annotationSource':'Unchanged Phase 2 expectedDocumentKeys; distinct document hits within original Top-5 chunks','summary':legacy_summary,'queries':legacy_metrics})
# All relevant chunk ranks and document ranks are recorded, not just averages.
for record in comparison:
    for strategy in strategies:
        hits=record['strategies'][strategy]['top5'];record['strategies'][strategy]['relevantDocumentRanks']={did:next((i for i,r in enumerate(hits,1) if r['documentId']==did),None) for did in record['relevantDocumentIds']}
        full=next(r for r in results['HYBRID' if strategy=='VECTOR' else strategy] if r['queryId']==record['queryId'])
        candidates=full['vectorCandidates' if strategy=='VECTOR' else 'candidates']
        record['strategies'][strategy]['relevantCandidateRanks']={cid:next((i for i,r in enumerate(candidates,1) if r['chunkId']==cid),None) for cid in record['relevantChunkIds']}
    record['hitTransitions']={s:{'before':record['strategies']['VECTOR']['metrics']['hitAt5'],'after':record['strategies'][s]['metrics']['hitAt5']} for s in ['HYBRID','HYBRID_RERANK']}
    record['rerankerChangesVsHybrid']={k:record['strategies']['HYBRID_RERANK']['metrics'][k]-record['strategies']['HYBRID']['metrics'][k] for k in ['hitAt5','recallAt5','mrrAt5','ndcgAt5']}
write('query-by-query-comparison.json',comparison)
summary['rerankerVsHybrid']={'improvedQueries':[r['queryId'] for r in comparison if any(v>0 for v in r['rerankerChangesVsHybrid'].values())],
    'worsenedQueries':[r['queryId'] for r in comparison if any(v<0 for v in r['rerankerChangesVsHybrid'].values())],
    'hitRecoveredQueries':[r['queryId'] for r in comparison if r['rerankerChangesVsHybrid']['hitAt5']>0],
    'hitLostQueries':[r['queryId'] for r in comparison if r['rerankerChangesVsHybrid']['hitAt5']<0]}
write('comparison-summary.json',summary)
download_path=dest/'model-download.log';raw=download_path.read_bytes();text=raw.decode('utf-16') if raw.startswith(b'\xff\xfe') else raw.decode('utf-8')
download=next(json.loads(line) for line in text.splitlines() if line.startswith('{"model":'))
write('model-artifacts.json',download)
env=read('environment.json');reg=read('regression-results.json');browser=read('browser-regression.json');assert reg['result']==browser['result']=='PASS'
audit=read('token-length-audit.json');assert audit['result']=='PASS' and audit['truncatedPairs']==0
assert read('experiment-verification.json')['result']=='PASS'
frozen=json.loads((root/'docs/phase7-baseline/sha256.json').read_text());assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
new=[]
for folder in ['retrieval-service','evaluation-service/retrieval_eval','evaluation-service/retrieval_tests','docs/phase7-baseline']:
    new += [p.relative_to(root).as_posix() for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
new += ['compose.phase8.yaml','evaluation-service/datasets/retrieval-v1.json','docs/phase8-result.md']
new += [p.relative_to(root).as_posix() for p in (root/'docs/scripts').glob('phase8-*.py')]
write('changed-files.json',{'changedExistingFiles':[],'addedFiles':sorted(new),'evidenceDirectory':'docs/phase8-evidence/','frozenFilesUnchanged':len(frozen)})
labels={'VECTOR':'Vector Baseline','LEXICAL':'Lexical only','HYBRID':'Hybrid (BM25 + RRF)','HYBRID_RERANK':'Hybrid + Reranker'}
def table(group,include_lexical=True):
    lines=['| Strategy | Hit@5 | Recall@5 | MRR@5 | nDCG@5 | mean ms | p50 ms | p95 ms | 실패 query |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in strategies:
        if not include_lexical and s=='LEXICAL':continue
        v=group[s];t=v['latencyMs'];lines.append(f"| {labels[s]} | {v['hitAt5']*100:.2f}% | {v['recallAt5']*100:.2f}% | {v['mrrAt5']:.4f} | {v['ndcgAt5']:.4f} | {t['mean']:.2f} | {t['p50']:.2f} | {t['p95']:.2f} | {v['failedQueries']} |")
    return lines
all_metrics=summary['groups']['all']
lines=['# Phase 8 검색 비교 결과','',
 f"Hybrid의 Recall@5는 {all_metrics['VECTOR']['recallAt5']*100:.2f}% → {all_metrics['HYBRID']['recallAt5']*100:.2f}%로 증가했고 p50 latency는 {all_metrics['VECTOR']['latencyMs']['p50']:.2f}ms → {all_metrics['HYBRID']['latencyMs']['p50']:.2f}ms였다. Hybrid+Reranker는 nDCG@5 {all_metrics['HYBRID_RERANK']['ndcgAt5']:.4f}로 가장 높지만 Recall@5 {all_metrics['HYBRID_RERANK']['recallAt5']*100:.2f}%는 Hybrid보다 낮고 p50 {all_metrics['HYBRID_RERANK']['latencyMs']['p50']:.2f}ms를 소모했다. 이 작은 CPU 실험에서 reranker의 비용 대비 이점은 제한적이며 기존 사용자 검색을 자동 교체하지 않았다.",'',
 '## 1. Vector Baseline 보존','',
 f"Phase 7 기준 소스 {len(frozen)}개 파일을 `docs/phase7-baseline/source.zip`과 SHA-256 목록으로 고정했다. 기존 파일 변경은 0개다. Phase 2의 기존 8개 query는 시작 시점·최종 비교·종료 시점 모두 Top-5 chunk 순위와 score가 **정확히 동일**했다. 허용 오차 비교가 아닌 숫자 equality로 검증했다.",'',
 'BGE-M3 모델/revision, 9 documents, 27 chunks, content, metadata, embedding 벡터 해시, 기존 similarity SQL을 보존했다. `VectorSearch.search`를 그대로 재사용하며 후보 20개를 위한 별도 내부 request 어댑터만 추가했다. 기존 API의 topK 제한과 사용자 Flow는 바꾸지 않았다.','',
 '## 2. Hybrid Search 설계','',
 '독립 `retrieval-service`는 rag_reader만 사용한다. 기존 Vector 검색과 별도 BM25를 실행하고 `1/(60+vectorRank)+1/(60+lexicalRank)`로 결합한다. 한 branch에 없는 항목은 그 branch 기여가 0이다. 원시 vector/BM25 score를 더하지 않는다. 동점은 chunkId로 정렬한다.','',
 'Kiwi(kiwipiepy 0.24.0) 형태소 분석으로 한국어 조사·어미 영향을 줄인다. 명사/용언/수식언/어근을 사용하고, 영문 API 식별자와 오류코드는 정규식으로 원형 단위 보존 후 소문자화한다. BM25 k1=1.5, b=0.75, RRF k=60, branch 후보 수=20, rerank 후보 수=20, 최종 Top-K=5를 결과 조회 전에 고정했다. 튜닝 횟수는 0이다. [Kiwi 공식 설명](https://github.com/bab2min/kiwipiepy)','',
 '## 3. Reranker 모델 및 선정 근거','',
 f"모델은 `{download['model']}`, revision `{download['revision']}`이다. 공식 모델 문서의 다국어 cross-encoder이며 별도 원격 코드 없이 Transformers로 로컬 실행할 수 있어 선택했다. 모델명·revision·batchSize=4·maxLength=512·CPU threads=4는 설정 파일로 관리한다. `RerankerProvider` 인터페이스와 `LocalRerankerProvider`를 분리했다. [공식 모델 카드](https://huggingface.co/BAAI/bge-reranker-v2-m3)",'',
 'Hybrid Top-20의 동일 contentSnippet에 대해서만 raw logit을 계산한다. CPU float32, eval/inference_mode를 사용하며 외부 추론 API는 없다. 실패·비정상 score는 HTTP 503 RERANKER_UNAVAILABLE이며 묵시적 fallback은 없다. 모델 파일별 SHA-256은 `model-artifacts.json`에 있다.','',
 '## 4. Evaluation dataset','',
 f"총 32 query = 기존 8개 + 신규 합성 24개. 모든 query마다 27 chunks를 0/1/2로 사전 판정했다. 2는 직접 답변, 1은 실질적 보조 근거, 0은 무관이다. queryId/queryText/relevantDocumentIds/relevantChunkIds/category/domain 및 모든 grade가 포함된다. Dataset SHA-256: `{freeze['datasetSha256']}`.",'',
 '새로운 검색용 annotation이며 기존 Phase 2의 expectedDocumentKeys 및 Phase 6 Ground Truth를 수정하지 않았다. 기존 8개의 legacy 문서 기대값은 별도로 보존한다. 평가 정답은 evaluation-service/datasets와 평가 산출물에만 존재하고 검색 컨테이너에 복사하거나 mount하지 않는다. 검색 API에는 queryId/queryText/strategy만 전달하며 label 필드는 422로 거부한다.','',
 '## 5. Metric 정의','',
 '- 평가 기본 단위는 chunk, relevant는 grade > 0이다. 문서 기준 결과와 섞지 않는다.',
 '- Hit@5: Top-5에 relevant chunk가 한 개 이상 있으면 1, 그 외 0; query macro average.',
 '- Recall@5: Top-5 relevant chunk 수 / 해당 query의 전체 relevant chunk 수; query macro average.',
 '- MRR@5: Top-5 내 첫 relevant rank의 역수. Top-5 밖은 0. 전체 27개에 대한 무절단 MRR은 아니다.',
 '- nDCG@5: DCG=sum((2^grade-1)/log2(rank+1)), 같은 query 전체 GT의 이상적 Top-5 DCG로 정규화.',
 '- Latency: 전체 query 1회 워밍업 뒤 각 전략/query 3회 실행. 전략당 96개 sample의 mean/p50/p95. 분위수는 (n-1)*p 선형 보간.',
 '- 실패 query: Hit@5=0. 빈 정답 분모는 N/A이며 100%로 간주하지 않는다.','',
 '## 6. 전체 비교 결과','',
 '동일 corpus/query/GT/finalTopK/embedding/프로세스에서 측정한 실제 값이다. Lexical은 보조 비교다.','']+table(summary['groups']['all'])+['','### 기존 Phase 2 query 8개','']+table(summary['groups']['phase2-original-8'])+['','### 추가 synthetic query 24개','']+table(summary['groups']['synthetic-24'])+['',
 '## 7. Query별 개선 및 악화','',
 '아래 개선/악화 목록은 4개 metric 중 하나라도 증가/감소한 경우다. 다른 metric이 반대 방향으로 움직이면 양쪽 목록에 들어갈 수 있다. 모든 query의 원문, 정답, Top-5, relevant rank와 성공/실패 변화는 `query-by-query-comparison.json`에 저장했다.','']
for s in ['HYBRID','HYBRID_RERANK']:
    lines += [f"- {labels[s]} 개선: "+', '.join(summary['improvedQueries'][s]),f"- {labels[s]} 악화: "+(', '.join(summary['worsenedQueries'][s]) or '없음')]
lines += ['- Reranker vs Hybrid 개선: '+(', '.join(summary['rerankerVsHybrid']['improvedQueries']) or '없음'),'- Reranker vs Hybrid 악화: '+(', '.join(summary['rerankerVsHybrid']['worsenedQueries']) or '없음')]
for qid in summary['rerankerVsHybrid']['hitLostQueries']:
    r=next(r for r in comparison if r['queryId']==qid)
    lines += ['',f"실제 검색 성공→실패 사례: **{qid}: {r['queryText']}**. Relevant chunk 후보 순위는 "+' → '.join(f"{labels[s]} {list(r['strategies'][s]['relevantCandidateRanks'].values())}" for s in ['VECTOR','HYBRID','HYBRID_RERANK'])+'. Hybrid가 Top-5로 복구한 근거를 reranker가 다시 Top-5 밖으로 밀어냈다.']
lines += ['','| Query | Vector Recall@5 | Hybrid Recall@5 | Rerank Recall@5 | Vector nDCG@5 | Hybrid nDCG@5 | Rerank nDCG@5 |','|---|---:|---:|---:|---:|---:|---:|']
for r in comparison:
    m={s:r['strategies'][s]['metrics'] for s in ['VECTOR','HYBRID','HYBRID_RERANK']}
    lines.append('| '+r['queryId']+' | '+' | '.join(f"{m[s][k]:.4f}" for k in ['recallAt5','ndcgAt5'] for s in ['VECTOR','HYBRID','HYBRID_RERANK'])+' |')
lines += ['','### 변경하지 않은 Phase 2 문서 기대값 기준','',
 '아래는 새 graded annotation을 사용하지 않고 Phase 2의 기존 expectedDocumentKeys를 그대로 사용한 별도 비교다. Recall 분자는 Top-5 chunks에 포함된 relevant document를 중복 제거한 수다. MRR은 첫 relevant 문서가 등장한 원래 chunk rank의 역수다. 위 chunk 기준 수치와 혼합하지 않는다.','',
 '| Strategy | Legacy Hit@5 | Legacy Document Recall@5 | MRR@5 |','|---|---:|---:|---:|']
for s,m in legacy_summary.items():lines.append(f"| {labels[s]} | {m['hitAt5']*100:.2f}% | {m['documentRecallAt5']*100:.2f}% | {m['mrrAt5']:.4f} |")
lines += ['','### 기존 누락 문서의 rank 변화','', 'rank는 해당 문서 chunk가 처음 등장하는 위치다. 후보 Top-20 밖은 미포함으로 표시한다. 기존 baseline 순위는 수정하지 않았다.','']
for case in weaknesses:
    lines.append(f"- {case['queryId']} / {case['missingDocumentKey']}: "+' → '.join(f"{labels[s]} {case['strategies'][s]['bestChunkRankForDocument'] or 'Top-20 밖'}" for s in ['VECTOR','HYBRID','HYBRID_RERANK']))
lines += ['','## 8. Latency 및 비용 trade-off','',
 f"실행 환경: Docker Linux {env['cpuCount']} CPUs, RAM {env['memoryBytes']/1024**3:.2f} GiB, CPU float32, inference threads=4. 서비스별 인위적 CPU/메모리 제한은 없다. 초기 요청·전체 워밍업은 steady-state 통계에서 제외했다. 최종 측정 동안 다른 테스트·모델 다운로드를 병행하지 않았다.",'',
 f"최초 모델 다운로드와 체크섬 계산: {download['downloadAndChecksumMs']/1000:.2f}초, 총 {download['totalBytes']/10**9:.3f} GB. 이는 매 query 비용이 아니다. 과금형 추론 API 호출은 0회이며 CPU/RAM/전력 비용은 별도다. 실험 후 메모리 관측값은 `resource-snapshot.jsonl`에 저장했으며 peak 메모리라고 주장하지 않는다.",'',
 '| 초기 요청 | Client ms | Search ms | Reranker model load ms |','|---|---:|---:|---:|']
for s,r in latency['initialRequests'].items():lines.append(f"| {labels[s]} | {r['clientLatencyMs']:.2f} | {r['latencyMs']:.2f} | {r.get('rerankerModelLoadMs') or 0:.2f} |")
ratio=summary['groups']['all']['HYBRID_RERANK']['latencyMs']['p50']/summary['groups']['all']['VECTOR']['latencyMs']['p50']
lines += ['',f"Hybrid+Reranker의 steady-state p50은 Vector의 {ratio:.2f}배다. 검색 latencyMs는 서비스 내부 검색 시간이며 clientLatencyMs는 직렬화·로컬 전송을 포함한다. 최초 엔진/토크나이저 준비는 client 첫 요청에 포함되고 initializationMs도 별도 기록한다. 초기 단계 Hybrid 실험에는 localhost 접속 지연이 있어 최종 실험은 IPv4 loopback을 사용했다. 본 표는 최종 실험의 service latency만 사용한다.",'',
 '## 9. 발견한 한계','',
 '- 9 documents / 27 chunks는 매우 작은 합성 corpus다. 후보 20개가 corpus 대부분을 포괄하므로 큰 corpus의 recall/latency로 일반화할 수 없다.',
 '- 32 query와 relevance는 이번 작업에서 corpus 내용을 바탕으로 구성한 단일 synthetic annotation이다. 독립적인 사람 검수·annotator 합의나 미공개 실사용 평가를 대체하지 않는다.',
 '- 원래 8개 query의 과거 검색 결과는 이미 알려져 있었다. 추가 24개는 결과 확인 전에 고정했으며 이후 정답/query/corpus를 수정하지 않았다.',
 '- query당 3회 반복은 PoC latency 관측이며 높은 부하·동시성·cold OS cache를 대표하지 않는다. 통계적 유의성을 주장하지 않는다.',
 '- 제목/section을 검색 입력에 추가하지 않고 기존 snippet과 동일한 본문을 사용한다. 미지원 전략·장애를 성공 결과로 대체하지 않는다.',
 f"- 실제 query/chunk 864쌍의 최대 길이는 {audit['maxPairTokens']} tokens로 512 제한 이내이며 truncation은 0건이다. 원본 chunk 최대 길이도 {audit['maxChunkCharacters']}자로 snippet 700자 제한보다 짧다.",
 '- Hybrid나 Reranker가 모든 query와 모든 metric을 개선한다고 주장하지 않는다. 악화 사례를 포함한 원시 결과를 보존했다.','',
 '## 10. Phase 0~7 회귀 결과','',
 f"자동 테스트 {reg['totalTests']}개 통과: 기존 Backend 84, RAG/Analysis/Generation Python 61, Evaluation 40, 신규 Retrieval 27, 신규 Metric 13. 실패/오류/skip 0. 기존 React 화면은 변경하지 않았으며 Chrome에서 Requirement/Analysis 조회, 승인 TC Dummy PASS/FAIL, 새로고침 후 이력 유지가 통과했다.",'',
 'app/rag/evaluation 권한 경계를 보존했고 추가 DB migration은 없다. 검색 역할은 rag_reader이며 app/evaluation SELECT 및 rag DELETE가 실제 거부된다. 기존 Evaluation snapshot 재현, 기존 승인/반려 JSON 보존, Phase 2 Top-5와 score의 정확한 일치를 확인했다.','',
 '## 11. 변경 파일 및 재현','',
 '기존 파일 변경 0개. 추가 파일 목록은 `phase8-evidence/changed-files.json`을 참조한다. 기존 사용자 API/UI/프롬프트/Dummy API는 그대로다.','',
 '1. 기존 Phase 7 서비스를 기동한 상태에서 `docker compose -p master -f compose.yaml -f compose.phase7-local.yaml -f compose.phase8.yaml build retrieval-service` 실행. 신규 이미지는 기존 `master-ai-service:latest`의 고정 환경을 재사용하며 baseline 파일 해시 검증으로 다른 소스를 거부한다.',
 '2. 모델 최초 준비: 같은 compose 인자로 `run --rm --no-deps -e HF_HUB_OFFLINE=0 -e TRANSFORMERS_OFFLINE=0 retrieval-service python -m retrieval.download`.',
 '3. 같은 compose 인자로 `up -d --no-deps retrieval-service`. 정상 추론은 offline이다.',
 '4. `python docs/scripts/phase8-run.py --stage final`. 기존 최종 결과가 있으면 reruns 하위에 저장하여 덮어쓰지 않는다. `--query-id`는 개별 query 진단용이며 unknown ID는 명시적 오류다.',
 '5. 개발용 API: `POST http://127.0.0.1:8010/internal/v1/retrieval` with queryId/queryText/strategy. queryId는 correlation ID이며 정답 목록 조회는 evaluation-side CLI에서만 수행한다.',
 '6. `phase8-regression.py`, `phase8-runtime.py`, `phase8-browser-regression.py`로 회귀·권한 경계를 검증한다.','',
 '## 12. 미해결 사항','',
 '이번 Phase 완료 조건을 막는 미해결 사항은 없다. 결과의 일반화 가능성은 위 synthetic corpus/annotation 한계 내에서 해석해야 한다. Query Rewrite, GraphRAG, MCP, fine-tuning, prompt 튜닝, Dummy 확대, 인증, Failure Analysis는 구현하지 않았다.','']
(root/'docs/phase8-result.md').write_text('\n'.join(lines),encoding='utf-8')
write('completion-summary.json',{'result':'PASS','phase':8,'queryCount':32,'corpusDocuments':9,'corpusChunks':27,'strategies':3,'auxiliaryLexical':True,'finalTopK':5,'repetitions':3,'totalTests':225,'originalFilesChanged':0,'baselineRankAndScoreExact':True,'datasetSha256':freeze['datasetSha256'],'metrics':summary['groups']['all'],'unresolved':[]})
print(json.dumps(summary['groups']['all'],ensure_ascii=False));print('PASS Phase 8 report complete')
