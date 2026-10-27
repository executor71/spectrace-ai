# 커밋 대상 독립 검증

사용자의 후속 커밋·Push 요청에 따라 `phase15/change-impact-analysis` 브랜치에서 선행 Graph 수정과 Phase 15를 분리했다.

- 선행 Graph 커밋: `692d8ae` (`fix(graph): synchronize committed requirements and distinguish graph states`), 21개 파일. Graph 테스트 28건 재통과.
- Phase 15 커밋: 변경 영향 분석 코드·마이그레이션·테스트·합성 증거만 포함한다. 공용 App/Icon/navigation/TestCasePolicy는 필요한 Phase 15 부분만 인덱스에 구성했다.
- 기존 Java 업그레이드, 기업용 UI 개편, 랜덤 예제, 반납 Dummy 실행 확장은 미커밋 작업으로 보존했다. 작업 파일을 이전 버전으로 되돌리지 않았다.
- Git 인덱스를 OS 임시 폴더로 내보내 독립 검증했다. 이 스냅샷은 Java 21, 별도 tmpfs PostgreSQL에서 Java 134건, Python 219건, 합계 **353건 통과**했다. 프론트엔드 Docker/TypeScript/Vite 빌드도 성공했다.
- 기존 전체 작업 트리의 382건 결과와 커밋 스냅샷 353건 결과를 구분한다. 차이 29건은 제외한 반납 실행 확장 테스트 24건과 랜덤 예제 단위 테스트 5건이다.
- `.env`, 키 파일, DB, 모델 캐시, node_modules, .venv, 임시 로그를 제외했다. 증거 JSON의 credential 계열 필드와 고정 비밀 패턴을 검사했고 발견되지 않았다. XLSX와 PNG는 요청된 합성 시연 증거다.
- 기존 Ground Truth/평가셋/정책 AllowList 변경 없음. Public origin은 이전 세션에서 사용자가 Push를 승인했으며 이번 확인에서도 Public이다. master 병합, 강제 Push, 이력 재작성 없음.

기존 문서의 ‘커밋/Push 없음’은 각 구현·검증 종료 당시의 기록이다. 이번 후속 Git 작업은 별도 단계로 수행한다. 정식 사람 검토 평가 미완료 등 기능 한계는 기존 평가 문서대로 유지한다.

수치 근거: `commit-validation.json`. 원시 로그·스냅샷은 OS 임시 폴더 `spectrace-phase15-commit`에만 저장했다.
