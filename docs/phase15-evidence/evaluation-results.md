# 평가 결과와 한계

평가 fixture는 `evaluation-fixture.json`에 실모델 호출 전에 고정했다. 기존 Ground Truth와 분리된 작성자 초안이며 **독립적인 사람 검토는 아직 수행하지 않았다**. 생성/LLM 컨테이너에 이 파일을 제공하지 않았다. 이 문서는 정식 성능 검증 완료를 주장하지 않는다.

대여 승인 역할 확장 합성 사례 1건:

| 항목 | 실제 결과 |
|---|---|
| 실제 Qwen 호출 | 1회, 모델 분석 39,612ms; Job 대기 868ms, 실행 39,658ms |
| 최초 모델 결과 | ADDED/REMOVED; 유지 조건을 놓침. 필수 유형 ADDED/UNCHANGED 포함률 1/2 |
| 응답 재사용 재검증 | Qwen 0회; 4,838ms, Job 대기 397ms, 실행 4,895ms |
| 최종 원문 보정 대응 | 부서장 유지, 자산관리 담당자 추가 제안, 자기 승인 금지 유지 (3/3 fixture 부합) |
| 영향 API | 실제 Graph의 API-LOAN-APPROVE 1건; fixture 후보 집합 P/R 1/1 |
| TC 후보 | 기존 Baseline TC 5건 REVIEW; 후보 ID 집합 P/R 1/1 |
| 조건 Evidence ID 유효성 | 인용된 ID 전부 저장/검색 근거에서 확인 |
| 신규 TC | TEMPLATE_UNSUPPORTED, Expected Result null, 자동 실행 false |
| 개발자 수정률 | 미측정. 자동 원문 보정과 실제 개발자의 판단 수정률은 다름 |

수치 JSON은 `evaluation-results.json`, 최초 실제 모델 결과는 `analysis-result.json`, 보정 후 저장 결과는 `final-analysis-result.json`, 별도 Job들은 `job-result.json`, `reprocessing-job.json`이다. 최초 오분류는 삭제하거나 정답으로 고치지 않았다.

이 수치는 단일 큐레이션 사례의 fixture 일치율이다. 일반 Condition Accuracy/Impact Precision/Recall을 100%로 주장할 근거가 아니다. TC ID 집합 일치는 각 테스트의 실제 수정 필요성을 검증한 것이 아니며 보수적 후보가 과다 포함될 수 있다. 의미 비교 모델의 자기 승인 금지 오분류와 제한적 도메인 보정 의존성이 주요 한계다. 실제 개발자 검토, 더 많은 독립 사례, 과도한 영향 후보 정밀도 평가가 후속으로 필요하다. Phase 11의 Graph 100% 결과를 Phase 15 성능으로 재사용하지 않았다.
