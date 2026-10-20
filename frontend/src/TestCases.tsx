import TestCaseReview from './TestCaseReview'
import { useEffect, useState } from 'react'
import type { Screen } from './navigation'

type Evidence = { documentId: string; chunkId: string; documentType: string; section: string; contentSnippet: string; score: number }
export type TestCase = { approvalStatus: string; reviewedAt: string | null; reviewer: string | null; reviewComment: string | null; reviewRevision: number; modified: boolean; generatedContent: unknown; reviewedContent: unknown; executionEligible: boolean; testCaseId: string; requirementId: string; type: string; scenario: string; preconditions: string[]; input: Record<string, unknown>; steps: string[]; expectedResult: { description: string; assertions: unknown[] }; evidence: Pick<Evidence, 'documentId' | 'chunkId'>[]; executable: boolean }
type Result = { generationId: string; testCases: TestCase[]; clarificationRequired: string[]; uncoveredTypes: string[]; sourceAnalysis: { evidence: Evidence[] }; stale: boolean; generationLatencyMs: number; llmCalls: number; executionDecisions: { testCaseId: string; gates: Record<string, boolean>; reason: string }[] }
const labels: Record<string, string> = { apiAllowListed: 'API AllowList', methodEndpointKnown: 'Method / Endpoint 확인', preconditionsReproducible: '사전조건 재현 가능', inputDefined: 'Input 정의', expectedResultCheckable: '코드 판정 가능' }

export default function TestCases({ requirementId, initialTc, view, onNavigate, onSummary }: { requirementId: string; initialTc?: string; view: Screen; onNavigate: (view: Screen) => void; onSummary: (value: { total: number; approved: number }) => void }) {
  const [result, setResult] = useState<Result | null>(null)
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [filter, setFilter] = useState('ALL')
  useEffect(() => {
    if (result) onSummary({ total: result.testCases.length, approved: result.testCases.filter(item => item.approvalStatus === 'APPROVED').length })
  }, [result, onSummary])
  async function reviewed(updated: TestCase) {
    setResult(previous => previous && ({ ...previous, testCases: previous.testCases.map(item => item.testCaseId === updated.testCaseId ? updated : item) }))
    try {
      const response = await fetch(`/api/requirements/${encodeURIComponent(requirementId)}/test-cases`, { signal: AbortSignal.timeout(15000) })
      if (!response.ok) throw new Error('검토는 저장되었지만 목록 갱신에 실패했습니다. 저장된 테스트를 다시 조회해 주세요.')
      setResult(await response.json())
    } catch (err) { setError(err instanceof Error ? err.message : '목록 갱신에 실패했습니다.') }
  }
  async function request(generate: boolean) {
    if (busy) return
    setBusy(true); setError(''); setNotice(''); setResult(null); setSelected('')
    try {
      const response = await fetch(`/api/requirements/${encodeURIComponent(requirementId)}/test-cases${generate ? '/generate' : ''}`, { method: generate ? 'POST' : 'GET', signal: AbortSignal.timeout(generate ? 660000 : 15000) })
      const body = await response.json().catch(() => null)
      if (!generate && response.status === 404) { setNotice('아직 생성된 테스트가 없습니다. 먼저 변경 요청 분석을 완료한 뒤 ‘테스트 자동 생성’을 눌러 주세요.'); return }
      if (!response.ok) throw new Error(body?.message || `테스트 요청에 실패했습니다. (HTTP ${response.status})`)
      if (!body || body.requirementId !== requirementId || !['testCases', 'clarificationRequired', 'uncoveredTypes', 'executionDecisions'].every(key => Array.isArray(body[key])) || !Array.isArray(body.sourceAnalysis?.evidence)) throw new Error('테스트 응답 형식이 올바르지 않습니다.')
      setNotice(body.testCases.length ? `저장된 테스트 ${body.testCases.length}건을 조회했습니다.` : '테스트 생성을 보류했습니다. 확정 조건·근거 또는 지원되는 테스트 유형이 부족합니다. 아래 사유를 읽고 요청 내용을 구체화해 새 변경 요청으로 저장한 뒤 다시 분석해 주세요.')
      setResult(body); setSelected(body.testCases.some((c: TestCase) => c.testCaseId === initialTc) ? initialTc ?? '' : body.testCases[0]?.testCaseId ?? '')
    } catch (err) { setError(err instanceof Error && err.name === 'TimeoutError' ? '응답 대기 시간이 초과되었습니다. 저장된 테스트 조회로 결과를 확인해 주세요.' : err instanceof Error ? err.message : '테스트 요청에 실패했습니다.') }
    finally { setBusy(false) }
  }
  useEffect(() => { void request(false) }, [requirementId])
  useEffect(() => { if (initialTc && result?.testCases.some(c => c.testCaseId === initialTc)) setSelected(initialTc) }, [initialTc, result])
  const current = result?.testCases.find(item => item.testCaseId === selected)
  const decision = result?.executionDecisions.find(item => item.testCaseId === selected)
  return <section className="test-cases" aria-labelledby="test-cases-heading">
    <div className="panel-title"><span className="eyebrow">TEST WORKBENCH</span><h2 id="test-cases-heading">{view === 'review' ? '테스트 검토·승인' : view === 'execution' ? '테스트 실행·결과 확인' : '테스트 자동 생성'}</h2></div>
    <p>저장된 분석의 확정 조건과 근거를 사용합니다. 확인이 필요한 조건은 별도로 표시합니다.</p>
    <div className="lookup-controls">
      <button type="button" disabled={busy} onClick={() => request(true)}>테스트 자동 생성</button>
      <button type="button" className="secondary" disabled={busy} onClick={() => request(false)}>저장된 테스트 조회</button>
    </div>
    {busy && <p role="status" className="loading-panel"><span className="spinner" /> 테스트 요청 처리 중…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!result && !busy && !notice && !error && <div className="card empty-state"><h3>저장된 테스트를 불러오세요</h3><p>테스트를 조회하면 시나리오 확인, 검토와 실행을 이어서 진행할 수 있습니다.</p></div>}
    {result && result.testCases.length > 0 && view === 'testcases' && <div className="guide-next"><p>생성된 시나리오와 기대결과를 확인한 뒤 개발자가 승인해야 실행할 수 있습니다.</p><button onClick={() => onNavigate('review')}>다음: 테스트 검토·승인</button></div>}
    {result && view === 'review' && result.testCases.some(tc => tc.approvalStatus === 'APPROVED') && <div className="guide-next"><p>승인된 테스트가 있습니다. 실행 가능 조건을 확인하고 직접 실행하세요.</p><button onClick={() => onNavigate('execution')}>다음: 테스트 실행·결과 확인</button></div>}
    {result && !result.testCases.length && <div className="guide-next"><p>근거가 부족하거나 확인할 조건이 남아 자동 생성을 진행할 수 없습니다. 분석의 확인 질문과 아래 사유를 확인하세요.</p><button className="secondary" onClick={() => onNavigate('analysis')}>변경 요청 분석으로 돌아가기</button></div>}
    {result && <div className="test-case-result">
      {result.stale && <p role="alert" className="form-error">분석 또는 정책이 변경되었습니다. 최신 분석으로 다시 생성해 주세요.</p>}
      <p>{result.testCases.length}개 테스트 · 생성 시간 {(result.generationLatencyMs / 1000).toFixed(1)}초</p>
      {!!result.clarificationRequired.length && <section aria-label="사용자 확인 필요"><h3>조건 확인이 필요하여 테스트 생성 보류</h3><ul>{result.clarificationRequired.map((text, i) => <li key={i}>{text}</li>)}</ul></section>}
      {!!result.uncoveredTypes.length && <p>생성되지 않은 유형: {result.uncoveredTypes.join(', ')}</p>}
      <div className="workflow-tabs" aria-label="테스트 작업 단계">{([{ id: 'testcases', label: '시나리오' }, { id: 'review', label: '테스트 검토·승인' }, { id: 'execution', label: '테스트 실행·결과 확인' }] as const).map(tab => <button type="button" key={tab.id} className={view === tab.id ? 'active' : ''} aria-current={view === tab.id ? 'page' : undefined} onClick={() => onNavigate(tab.id)}>{tab.label}</button>)}</div>
      <div className="test-workbench"><div className="card test-list-card"><div className="card-heading"><h3>테스트 목록</h3><span className="count-chip">{result.testCases.length}</span></div><label htmlFor="test-type-filter" className="sr-only">테스트 유형 필터</label><select id="test-type-filter" value={filter} onChange={e => setFilter(e.target.value)}><option value="ALL">모든 유형</option>{['NORMAL', 'EXCEPTION', 'AUTHORIZATION', 'BOUNDARY', 'BUSINESS_RULE'].map(type => <option key={type}>{type}</option>)}</select><ul className="test-case-list">{result.testCases.filter(item => filter === 'ALL' || item.type === filter).map(item => <li key={item.testCaseId}><button type="button" aria-pressed={selected === item.testCaseId} onClick={() => setSelected(item.testCaseId)}><span className={`type-tag type-${item.type}`}>{item.type}</span><strong>{item.scenario}</strong><span className="test-row-meta"><span className={`status-badge status-${item.approvalStatus}`}>{item.approvalStatus}</span><small>Revision {item.reviewRevision}</small></span></button></li>)}</ul>{!result.testCases.filter(item => filter === 'ALL' || item.type === filter).length && <p className="empty-hint">해당 유형의 테스트가 없습니다.</p>}</div>
      {current && <article className="card test-case-detail" aria-label="테스트 상세">
        <span className={`type-tag type-${current.type}`}>{current.type}</span><h3>{current.scenario}</h3><span className={`status-badge status-${current.approvalStatus}`}>{current.approvalStatus}</span>
        <p className="metadata">TC ID: {current.testCaseId} · Revision {current.reviewRevision}</p>
        <TestCaseReview key={current.testCaseId + ":" + current.reviewRevision} current={current} stale={result.stale} onSaved={reviewed} reviewVisible={view === 'review'} executionVisible={view === 'execution'} />
        <div hidden={view !== 'testcases'} className="test-scenario-content">
        <details><summary>생성 단계의 실행 가능성 기록</summary><p>{decision?.reason}</p><ul>{Object.entries(decision?.gates ?? {}).map(([key, value]) => <li key={key}>{labels[key] ?? key}: {String(value)}</li>)}</ul></details>
        <h4>사전조건</h4><ul>{current.preconditions.map((text, i) => <li key={i}>{text}</li>)}</ul>
        <h4>입력</h4><pre>{JSON.stringify(current.input, null, 2)}</pre>
        <h4>절차</h4><ol>{current.steps.map((text, i) => <li key={i}>{text}</li>)}</ol>
        <h4>기대결과</h4><p>{current.expectedResult.description}</p><pre>{JSON.stringify(current.expectedResult.assertions, null, 2)}</pre>
        <h4>분석 근거</h4><div className="test-case-evidence">{current.evidence.map(ref => {
          const source = result.sourceAnalysis.evidence.find(e => e.documentId === ref.documentId && e.chunkId === ref.chunkId)
          return <details key={ref.chunkId}><summary>{source?.documentType} · {source?.section}</summary><p>documentId: {ref.documentId}<br />chunkId: {ref.chunkId}<br />score: {source?.score}</p><p>{source?.contentSnippet ?? '저장된 근거를 확인할 수 없습니다.'}</p></details>
        })}</div><div className="detail-actions"><button type="button" onClick={() => onNavigate('review')}>테스트 검토·승인으로 이동</button><button type="button" className="secondary" onClick={() => onNavigate('execution')}>실행 결과 보기</button></div></div>
      </article>}
      </div>
    </div>}
  </section>
}
