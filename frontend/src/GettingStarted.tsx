import type { Screen } from './navigation'

export const exampleRequest = {
  title: '부서장 대여 승인 및 자기 승인 금지 검증',
  description: '요청자 소속 부서의 부서장만 대여 신청을 승인할 수 있다.\n\n대여 신청자가 본인의 신청을 직접 승인하는 것은 허용하지 않는다.\n\n승인 권한이 없는 사용자의 요청은 거부되어야 한다.\n\n동일 자산에 대한 중복 승인도 허용하지 않는다.',
}

export default function GettingStarted({ onExample, onNavigate, next, selectedTitle, disabled }: {
  onExample: () => void; onNavigate: (screen: Screen) => void; next: Screen; selectedTitle?: string; disabled: boolean
}) {
  const nextLabels: Partial<Record<Screen,string>> = {
    requirements: '변경 요청 입력하기', analysis: '변경 요청 분석하기', testcases: '테스트 자동 생성으로 이동',
    review: '테스트 검토·승인으로 이동', execution: '테스트 실행·결과 확인으로 이동',
  }
  return <section className="getting-started" aria-labelledby="getting-started-title">
    <div className="guide-heading"><div><p className="eyebrow">처음 사용하는 분을 위한 안내</p><h2 id="getting-started-title">변경 요청부터 검증까지, 네 단계</h2></div><span className="guide-synthetic">합성 IT 자산관리 체험</span></div>
    <ol className="guide-steps" aria-label="4단계 업무 흐름">
      <li><span>1</span><div><strong>변경 요청 입력</strong><small>바꾸려는 업무조건을 적고 저장합니다.</small></div></li>
      <li><span>2</span><div><strong>AI 분석 및 테스트 생성</strong><small>관련 업무규칙을 분석한 뒤 테스트를 생성합니다.</small></div></li>
      <li><span>3</span><div><strong>개발자 검토·승인</strong><small>조건과 기대결과를 검토하고 승인합니다.</small></div></li>
      <li><span>4</span><div><strong>테스트 실행·결과 확인</strong><small>승인된 테스트를 실행하고 기대결과와 비교합니다.</small></div></li>
    </ol>
    <div className="guide-bottom"><div><p>{selectedTitle ? `현재 선택: ${selectedTitle}` : '무엇을 입력할지 막막하다면, 대여 승인 권한 예제로 시작하세요.'}</p><small>예제 불러오기는 입력폼만 채웁니다. 저장·분석·생성·실행은 각 단계에서 직접 시작합니다.</small></div><div className="guide-actions"><button className="secondary" disabled={disabled} onClick={onExample}>예제 불러오기</button><button disabled={disabled} onClick={() => onNavigate(next)}>다음: {nextLabels[next] ?? '변경 요청 입력하기'} <span aria-hidden="true">→</span></button></div></div>
  </section>
}

export function TechnicalGuide() {
  return <details className="technical-guide"><summary>기술 용어와 검증 범위 알아보기</summary><p>이 영역은 개발·관리자를 위한 기술 검증입니다. 일반 변경 요청의 분석·검토·실행과 별도로 확인할 수 있습니다.</p><dl><dt>RAG · 관련 자료 검색</dt><dd>저장된 업무규칙과 API 자료를 찾아 AI 분석의 근거로 사용합니다.</dd><dt>Ground Truth · 고정 비교 기준</dt><dd>등록된 합성 예제의 기준 답안과 저장 결과를 비교합니다. 모든 변경 요청에 점수를 매기는 기능은 아닙니다.</dd><dt>MCP · 도구 연결 규약</dt><dd>외부 개발 도구가 허용된 조회 기능을 사용할 때의 연결 규약입니다.</dd><dt>OTel · 처리 과정 추적</dt><dd>요청 처리 시간과 서비스 간 흐름을 추적하는 운영 도구입니다.</dd></dl><p>테스트 실행은 합성 API 환경에서 수행합니다. 실제 운영 시스템을 변경하거나 실제 업무시간 절감률을 측정한 결과는 아닙니다.</p></details>
}
