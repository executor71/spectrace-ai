# 가상 IT 자산관리 Knowledge Base

모든 인물, 조직, 규칙, API 및 오류 코드는 Phase 2 검색 검증을 위한 합성 자료다. 실제 회사의 정책이나 운영 문서를 포함하지 않는다.

`manifest.json`에 명시된 Markdown 문서만 초기 적재 대상이다. 각 `##` 섹션은 하나의 독립된 업무 의미 단위이며 chunk 경계다. 문서 제목·section을 본문 앞에 붙여 embedding 입력을 만든다. 문서 ID와 chunk ID는 문서 key/version/section으로부터 UUIDv5로 생성한다.

검색 검증 질의는 AI 테스트 fixture에 별도로 보관하며 이 manifest와 chunk 입력에 포함하지 않는다. evaluation schema의 자료는 읽거나 적재하지 않는다.
