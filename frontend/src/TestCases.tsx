import TestCaseReview from './TestCaseReview'
import { useState } from 'react'

type Evidence = { documentId: string; chunkId: string; documentType: string; section: string; contentSnippet: string; score: number }
export type TestCase = { approvalStatus: string; reviewedAt: string | null; reviewer: string | null; reviewComment: string | null; reviewRevision: number; modified: boolean; generatedContent: unknown; reviewedContent: unknown; executionEligible: boolean; testCaseId: string; requirementId: string; type: string; scenario: string; preconditions: string[]; input: Record<string, unknown>; steps: string[]; expectedResult: { description: string; assertions: unknown[] }; evidence: Pick<Evidence, 'documentId' | 'chunkId'>[]; executable: boolean }
type Result = { generationId: string; testCases: TestCase[]; clarificationRequired: string[]; uncoveredTypes: string[]; sourceAnalysis: { evidence: Evidence[] }; stale: boolean; generationLatencyMs: number; llmCalls: number; executionDecisions: { testCaseId: string; gates: Record<string, boolean>; reason: string }[] }
const labels: Record<string, string> = { apiAllowListed: 'API AllowList', methodEndpointKnown: 'Method / Endpoint 확인', preconditionsReproducible: '사전조건 재현 가능', inputDefined: 'Input 정의', expectedResultCheckable: '코드 판정 가능' }

export default function TestCases({ requirementId }: { requirementId: string }) {
  const [result, setResult] = useState<Result | null>(null)
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
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
      if (!generate && response.status === 404) { setNotice('저장된 테스트가 없습니다. (HTTP 404)'); return }
      if (!response.ok) throw new Error(body?.message || `테스트 요청에 실패했습니다. (HTTP ${response.status})`)
      if (!body || body.requirementId !== requirementId || !['testCases', 'clarificationRequired', 'uncoveredTypes', 'executionDecisions'].every(key => Array.isArray(body[key])) || !Array.isArray(body.sourceAnalysis?.evidence)) throw new Error('테스트 응답 형식이 올바르지 않습니다.')
      setNotice(body.testCases.length ? `저장된 테스트 ${body.testCases.length}건을 조회했습니다.` : '조회는 성공했지만 저장된 테스트케이스가 0건입니다. 아래 생성 보류 사유와 미생성 유형을 확인해 주세요.')
      setResult(body); setSelected(body.testCases[0]?.testCaseId ?? '')
    } catch (err) { setError(err instanceof Error && err.name === 'TimeoutError' ? '응답 대기 시간이 초과되었습니다. 저장된 테스트 조회로 결과를 확인해 주세요.' : err instanceof Error ? err.message : '테스트 요청에 실패했습니다.') }
    finally { setBusy(false) }
  }
  const current = result?.testCases.find(item => item.testCaseId === selected)
  const decision = result?.executionDecisions.find(item => item.testCaseId === selected)
  return <section className="test-cases" aria-labelledby="test-cases-heading">
    <h2 id="test-cases-heading">근거 기반 테스트 케이스</h2>
    <p>저장된 분석의 확정 조건과 근거를 사용합니다. 확인이 필요한 조건은 별도로 표시합니다.</p>
    <div className="lookup-controls">
      <button type="button" disabled={busy} onClick={() => request(true)}>테스트 생성</button>
      <button type="button" disabled={busy} onClick={() => request(false)}>저장된 테스트 조회</button>
    </div>
    {busy && <p role="status">테스트 요청 처리 중…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {result && <div className="test-case-result">
      {result.stale && <p role="alert" className="form-error">분석 또는 정책이 변경되었습니다. 최신 분석으로 다시 생성해 주세요.</p>}
      <p>{result.testCases.length}개 테스트 · 생성 시간 {(result.generationLatencyMs / 1000).toFixed(1)}초</p>
      {!!result.clarificationRequired.length && <section aria-label="사용자 확인 필요"><h3>사용자 확인 필요 · 생성 보류</h3><ul>{result.clarificationRequired.map((text, i) => <li key={i}>{text}</li>)}</ul></section>}
      {!!result.uncoveredTypes.length && <p>생성되지 않은 유형: {result.uncoveredTypes.join(', ')}</p>}
      <ul className="test-case-list">{result.testCases.map(item => <li key={item.testCaseId}><button aria-pressed={selected === item.testCaseId} onClick={() => setSelected(item.testCaseId)}>{item.type} · {item.scenario} · {item.approvalStatus}</button></li>)}</ul>
      {current && <article className="test-case-detail" aria-label="테스트 상세">
        <h3>{current.type} · {current.scenario}</h3>
        <p>ID: {current.testCaseId}</p>
        <TestCaseReview key={current.testCaseId + ":" + current.reviewRevision} current={current} stale={result.stale} onSaved={reviewed} />
        <details><summary>생성 단계의 실행 가능성 기록</summary><p>{decision?.reason}</p><ul>{Object.entries(decision?.gates ?? {}).map(([key, value]) => <li key={key}>{labels[key] ?? key}: {String(value)}</li>)}</ul></details>
        <h4>사전조건</h4><ul>{current.preconditions.map((text, i) => <li key={i}>{text}</li>)}</ul>
        <h4>입력</h4><pre>{JSON.stringify(current.input, null, 2)}</pre>
        <h4>절차</h4><ol>{current.steps.map((text, i) => <li key={i}>{text}</li>)}</ol>
        <h4>기대결과</h4><p>{current.expectedResult.description}</p><pre>{JSON.stringify(current.expectedResult.assertions, null, 2)}</pre>
        <h4>분석 근거</h4><div className="test-case-evidence">{current.evidence.map(ref => {
          const source = result.sourceAnalysis.evidence.find(e => e.documentId === ref.documentId && e.chunkId === ref.chunkId)
          return <details key={ref.chunkId}><summary>{source?.documentType} · {source?.section}</summary><p>documentId: {ref.documentId}<br />chunkId: {ref.chunkId}<br />score: {source?.score}</p><p>{source?.contentSnippet ?? '저장된 근거를 확인할 수 없습니다.'}</p></details>
        })}</div>
      </article>}
    </div>}
  </section>
}
