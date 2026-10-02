import { useEffect, useState } from 'react'
import type { TestCase } from './TestCases'

type Eligibility = { approvalStatus: string; executable: boolean; fixtureReady: boolean; executionEligible: boolean; apiId: string | null; blockedReason: string | null; syntheticDefect: boolean }
type Execution = { executionId: string; result: 'PASS' | 'FAIL' | 'ERROR'; executedAt: string; testCaseRevision: number; durationMs: number; expected: unknown; actual: unknown; mismatches: unknown[]; evidence: unknown; sourceEvidence: unknown; apiSpecEvidence?: unknown; syntheticDefect: boolean }
export default function TestCaseExecutions({ current, dirty }: { current: TestCase; dirty: boolean }) {
  const [eligibility, setEligibility] = useState<Eligibility | null>(null)
  const [history, setHistory] = useState<Execution[]>([])
  const [selected, setSelected] = useState<Execution | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const base = `/api/test-cases/${encodeURIComponent(current.testCaseId)}`
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setEligibility(null); setHistory([]); setSelected(null); setError('')
      try {
        const responses = await Promise.all([fetch(base + '/execution-eligibility', { signal: controller.signal }), fetch(base + '/executions', { signal: controller.signal })])
        const [status, runs] = await Promise.all(responses.map(r => r.json()))
        if (!responses.every(r => r.ok)) throw new Error(status.message || runs.message || '실행 이력 조회 실패')
        if (!controller.signal.aborted) { setEligibility(status); setHistory(runs); setSelected(runs[0] ?? null) }
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '조회 실패') }
    }
    void load()
    return () => controller.abort()
  }, [base, current.reviewRevision])
  async function execute() {
    if (busy || dirty || !eligibility?.executionEligible) return
    setBusy(true); setError('')
    try {
      const response = await fetch(base + '/executions', { method: 'POST', signal: AbortSignal.timeout(15000) })
      const value = await response.json()
      if (!response.ok) { setEligibility(null); throw new Error(`${value.code}: ${value.message}`) }
      setSelected(value); setHistory(previous => [value, ...previous])
    } catch (e) { setError(e instanceof Error ? e.message : '실행 실패. 저장된 결과는 다시 조회할 수 있습니다.') }
    finally { setBusy(false) }
  }
  return <section className="test-case-executions" aria-label="Dummy API 실행">
    <h4>Dummy API 실행</h4>
    {eligibility && <>
      <p className="execution-eligibility">approvalStatus: {eligibility.approvalStatus} · executable: {String(eligibility.executable)} · fixtureReady: {String(eligibility.fixtureReady)} · executionEligible: {String(eligibility.executionEligible)}</p>
      <p>대상 API: {eligibility.apiId ?? '허용되지 않음'}{eligibility.blockedReason && ` · 차단: ${eligibility.blockedReason}`}</p>
      {eligibility.syntheticDefect && <p role="note">합성 평가용 의도적 결함: 자기 승인 검사를 누락하는 fixture입니다.</p>}
    </>}
    <button type="button" disabled={busy || dirty || !eligibility?.executionEligible} onClick={execute}>Dummy 실행</button>
    {busy && <p role="status">실행 중…</p>}
    {error && <p role="alert">{error}</p>}
    <ul className="execution-history">{history.map(run => <li key={run.executionId}><button type="button" onClick={() => setSelected(run)}>{run.result} · {new Date(run.executedAt).toLocaleString('ko-KR')} · revision {run.testCaseRevision}</button></li>)}</ul>
    {selected && <div className="execution-result">
      <h4>실행 결과: <strong>{selected.result}</strong></h4>
      <p>실행 ID: {selected.executionId}</p><p>실행시간: {selected.durationMs} ms · TC revision: {selected.testCaseRevision}</p>
      {selected.testCaseRevision !== current.reviewRevision && <p>현재 TC와 revision이 다른 과거 실행 결과입니다.</p>}
      {selected.syntheticDefect && <p>합성 테스트용 의도적 결함 fixture 실행</p>}
      <h5>Expected</h5><pre>{JSON.stringify(selected.expected, null, 2)}</pre>
      <h5>Actual</h5><pre>{JSON.stringify(selected.actual, null, 2)}</pre>
      <h5>Mismatch</h5><pre>{JSON.stringify(selected.mismatches, null, 2)}</pre>
      <details><summary>실행 당시 관련 evidence</summary><pre>{JSON.stringify({ apiSpecification: selected.apiSpecEvidence, references: selected.evidence, sources: selected.sourceEvidence }, null, 2)}</pre></details>
    </div>}
  </section>
}
