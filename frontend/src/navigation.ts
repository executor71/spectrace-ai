export const screens = [
  { id: 'dashboard', label: '대시보드', path: 'Overview', description: '요구사항부터 실행 결과까지, 근거로 연결하는 검증 워크스페이스' },
  { id: 'requirements', label: '요구사항 관리', path: 'Requirements', description: '변경할 업무를 정의하고, 검증의 시작점을 만드세요.' },
  { id: 'analysis', label: 'AI 요구사항 분석', path: 'AI Analysis', description: '업무조건과 불확실성을 구분하고 원문 Evidence를 확인하세요.' },
  { id: 'testcases', label: '테스트케이스', path: 'Test Cases', description: '근거에서 도출한 테스트 시나리오를 한눈에 확인하세요.' },
  { id: 'review', label: '검토 및 승인', path: 'Review & Approval', description: '테스트의 내용을 검토하고 실행 전 승인 상태를 관리하세요.' },
  { id: 'execution', label: '실행 및 검증', path: 'Execution', description: '승인된 테스트를 실행하고 Expected와 Actual을 비교하세요.' },
  { id: 'evaluation', label: 'Ground Truth 평가', path: 'Evaluation', description: 'Frozen 평가셋을 기준으로 검색과 테스트의 품질을 측정하세요.' },
  { id: 'graph', label: 'Knowledge Graph', path: 'Knowledge Graph', description: '요구사항, 업무규칙, API와 테스트의 연결을 추적하세요.' },
] as const
export type Screen = typeof screens[number]['id']
