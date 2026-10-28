export const screens = [
  { id: 'dashboard', label: '대시보드', path: '업무 현황', description: '변경 요구사항의 근거 추적부터 테스트 설계, 검토 승인, 실행 및 평가까지. 검증 업무의 현황과 후속 조치를 관리합니다.' },
  { id: 'impact', label: '변경 영향 분석', path: '변경안 비교·검토', description: '기존 조건과 변경 제안을 비교하고 실제 근거·관계를 통해 API와 테스트의 검토 후보를 확인합니다.' },
  { id: 'requirements', label: '변경 요청 입력', path: '요구사항 등록·조회', description: '변경 목적과 업무조건을 등록하고, 검증할 요구사항을 선택합니다.' },
  { id: 'analysis', label: '변경 요청 분석', path: '근거 기반 분석', description: '확인된 조건과 누락·모호한 항목을 구분하고, 판단의 근거 문서를 추적합니다.' },
  { id: 'testcases', label: '테스트 자동 생성', path: '테스트 설계', description: '요구사항과 업무규칙을 기준으로 테스트 시나리오와 기대결과를 구성합니다.' },
  { id: 'review', label: '테스트 검토·승인', path: '검토·승인', description: '테스트의 적합성을 검토하고 수정 이력, 승인 상태와 실행 가능 여부를 확인합니다.' },
  { id: 'execution', label: '테스트 실행·결과 확인', path: '실행·결과', description: '승인된 테스트를 실행하고 기대결과와 실제 결과의 차이 및 실행 이력을 확인합니다.' },
  { id: 'evaluation', label: '품질 평가·관리', path: '품질 평가', description: '고정된 합성 기준으로 검색·시나리오·테스트 품질을 평가하고 결과를 비교합니다.' },
  { id: 'graph', label: '변경 영향 관계 확인', path: '변경 영향 추적', description: '요구사항, 업무규칙, API, 테스트와 실행 결과 사이의 연결 및 변경 영향을 추적합니다.' },
] as const
export type Screen = typeof screens[number]['id']
