export const screens = [
  { id: 'dashboard', label: '대시보드', path: '업무 현황', description: '프로그램 변경 요청을 입력하면 AI가 관련 업무규칙을 찾아 분석하고, 필요한 테스트를 생성하며, 승인된 테스트를 실행해 결과까지 검증하는 개발자용 업무 지원 시스템' },
  { id: 'impact', label: '변경 영향 분석', path: '변경안 비교·검토', description: '기존 조건과 변경 제안을 비교하고 실제 근거·관계를 통해 API와 테스트의 검토 후보를 확인합니다.' },
  { id: 'requirements', label: '변경 요청 입력', path: '변경 요청', description: '변경할 업무를 정의하고, 검증의 시작점을 만드세요.' },
  { id: 'analysis', label: '변경 요청 분석', path: '변경 요청 분석', description: '업무조건과 불확실성을 구분하고 업무규칙 원문을 확인하세요.' },
  { id: 'testcases', label: '테스트 자동 생성', path: '테스트 생성', description: '근거에서 도출한 테스트 시나리오를 한눈에 확인하세요.' },
  { id: 'review', label: '테스트 검토·승인', path: '검토·승인', description: '테스트의 내용을 검토하고 실행 전 승인 상태를 관리하세요.' },
  { id: 'execution', label: '테스트 실행·결과 확인', path: '실행·결과', description: '승인된 테스트를 실행하고 Expected와 Actual을 비교하세요.' },
  { id: 'evaluation', label: '기술 검증·관리', path: '기술 검증', description: '등록된 합성 예제로 품질을 비교하고, 기술 용어와 검증 범위를 확인하세요.' },
  { id: 'graph', label: '변경 영향 관계 확인', path: '변경 영향 관계', description: '요구사항, 업무규칙, API와 테스트의 연결을 추적하세요.' },
] as const
export type Screen = typeof screens[number]['id']
