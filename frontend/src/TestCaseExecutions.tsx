import { useEffect, useState } from 'react'
import type { TestCase } from './TestCases'

type Eligibility = { approvalStatus: string; executable: boolean; fixtureReady: boolean; executionEligible: boolean; apiId: string | null; blockedReason: string | null; syntheticDefect: boolean; returnFixtureOptions?: string[]; executionContractVersion?: string }
type Execution = { executionId: string; result: 'PASS' | 'FAIL' | 'ERROR'; executedAt: string; testCaseRevision: number; durationMs: number; expected: unknown; actual: unknown; mismatches: unknown[]; evidence: unknown; sourceEvidence: unknown; apiSpecEvidence?: unknown; syntheticDefect: boolean; apiId?: string; errorCode?: string; errorStage?: string; request?: { fixtureProfile?: string; method?: string; path?: string }; testCaseSnapshot?: { scenario?: string }; executionContractVersion?: string }
const reasons: Record<string,string> = { NOT_APPROVED: '승인 대기: 현재 수정본을 검토·승인해야 합니다.', NOT_EXECUTABLE: '실행 정의가 유효하지 않거나 분석·정책이 변경되었습니다.', FIXTURE_NOT_READY: 'Fixture 미지원 또는 미준비: 지원되는 실행 데이터를 준비하고 다시 승인하세요.', API_NOT_ALLOWED: 'API AllowList에 등록되지 않은 경로입니다.', EXECUTION_CONTRACT_UNSUPPORTED: '현재 TC의 실행 계약이 미지원이거나 준비한 계약과 다릅니다.', REVIEW_CONFLICT: '선택한 승인 Revision이 변경되었습니다. 다시 조회하세요.' }
const fixtureNames: Record<string,string> = { standard: '정상 계약 Fixture', 'asset-admin': '자산 담당자 정상 접수', 'completed-return': '검사 완료 후 중복 반납', 'intentional-defect': '의도적 결함 검증 · 검사 전 AVAILABLE 전이', 'fixture-error': '인프라 ERROR 검증 · Fixture 초기화 오류' }
export default function TestCaseExecutions({ current, dirty, onPrepared }: { current: TestCase; dirty: boolean; onPrepared: (updated:TestCase)=>void | Promise<void> }) {
  const [eligibility, setEligibility] = useState<Eligibility | null>(null)
  const [history, setHistory] = useState<Execution[]>([])
  const [selected, setSelected] = useState<Execution | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [profile,setProfile] = useState('standard')
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
      const response = await fetch(base + '/executions', { method: 'POST', headers: { 'If-Match': String(current.reviewRevision) }, signal: AbortSignal.timeout(15000) })
      const value = await response.json()
      if (!response.ok) { setEligibility(null); throw new Error(`${value.code}: ${value.message}`) }
      setSelected(value); setHistory(previous => [value, ...previous])
    } catch (e) { setError(e instanceof Error ? e.message : '실행 실패. 저장된 결과는 다시 조회할 수 있습니다.') }
    finally { setBusy(false) }
  }
  async function prepare() {
    if(busy || dirty)return
    setBusy(true);setError('')
    try {
      const response=await fetch(base+'/return-execution-setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reviewRevision:current.reviewRevision,fixtureProfile:profile}),signal:AbortSignal.timeout(15000)})
      const updated=await response.json()
      if(!response.ok)throw new Error(updated.message || '반납 실행 준비 실패')
      await onPrepared(updated)
    }catch(e){setError(e instanceof Error?e.message:'반납 실행 준비 실패')}finally{setBusy(false)}
  }
  return <section className="test-case-executions" aria-label="합성 API 테스트 실행">
    <h4>실행 가능 여부</h4><p>승인된 테스트를 합성 API 환경에서 실행해 기대결과와 실제결과를 비교합니다. 실제 운영 데이터는 변경하지 않습니다.</p>
    {eligibility && <>
      <div className="eligibility-grid"><span>승인 상태 <b className={`status-badge status-${eligibility.approvalStatus}`}>{eligibility.approvalStatus}</b></span><span>실행 정의 <b>{eligibility.executable ? '충족' : '미충족'}</b></span><span>합성 실행 데이터 <b>{eligibility.fixtureReady ? '준비됨' : '준비 안 됨'}</b></span><span>최종 실행 판정 <b>{eligibility.executionEligible ? '실행 가능' : '실행 불가'}</b></span></div>
      <p>대상 API: {eligibility.apiId ?? '허용되지 않음'}{eligibility.blockedReason && ` · ${reasons[eligibility.blockedReason] ?? eligibility.blockedReason}`}</p>
      {eligibility.syntheticDefect && <p role="note">의도적 결함 검증 / 합성 오류 주입 Fixture입니다. 일반 실행 집계와 구분됩니다.</p>}
      {!!eligibility.returnFixtureOptions?.length && <fieldset className="return-execution-setup" disabled={busy || dirty}><legend>반납 실행 Fixture 준비</legend><label htmlFor={'return-profile-'+current.testCaseId}>검토할 실행 모드</label><select id={'return-profile-'+current.testCaseId} value={profile} onChange={event=>setProfile(event.target.value)}>{eligibility.returnFixtureOptions.map(mode=><option key={mode} value={mode}>{fixtureNames[mode] ?? mode}</option>)}</select><p>준비 시 실행 계약과 기대결과가 검토본에 반영되며 DRAFT로 돌아갑니다. 다음 단계에서 개발자가 별도로 재승인해야 합니다. 실제 실행은 수행하지 않습니다.</p><button type="button" className="secondary" onClick={prepare}>반납 실행 Fixture 준비</button></fieldset>}
    </>}
    <button type="button" disabled={busy || dirty || !eligibility?.executionEligible} onClick={execute}>테스트 실행</button>
    {busy && <p role="status"><span className="spinner" /> 실행 중…</p>}
    {error && <p role="alert">{error} 연결 실패·실행 차단은 업무 검증 FAIL과 다릅니다. 저장된 실행 이력을 재조회하세요.</p>}
    <h4>실행 이력</h4>{eligibility && !history.length && <p className="empty-hint">저장된 실행 이력이 없습니다.</p>}
    <ul className="execution-history">{history.map(run => <li key={run.executionId}><button type="button" onClick={() => setSelected(run)}><span className={`status-badge status-${run.result}`}>{run.result}</span> · {new Date(run.executedAt).toLocaleString('ko-KR')} · revision {run.testCaseRevision}</button></li>)}</ul>
    {selected && <div className="execution-result">
      <h4>실행 결과: <strong className={`status-badge status-${selected.result}`}>{selected.result}</strong></h4>
      <p>실행 ID: {selected.executionId}</p><p>실행시간: {selected.durationMs} ms · TC revision: {selected.testCaseRevision}</p>
      <p>시나리오: {selected.testCaseSnapshot?.scenario ?? current.scenario}<br />API: {selected.apiId} · {selected.request?.method} {selected.request?.path}<br />Fixture: {selected.request?.fixtureProfile ?? 'standard'} · {selected.executedAt && new Date(selected.executedAt).toLocaleString('ko-KR')}</p>
      {selected.result==='ERROR' && <p role="alert">인프라 처리 오류: {selected.errorCode} · {selected.errorStage ?? 'DUMMY_INVOCATION'} (업무 결과 FAIL이 아닙니다.)</p>}
      {selected.testCaseRevision !== current.reviewRevision && <p>현재 TC와 revision이 다른 과거 실행 결과입니다.</p>}
      {selected.syntheticDefect && <p>합성 테스트용 의도적 결함 fixture 실행</p>}
      <div className="execution-comparison"><section><h5>Expected · 기대결과</h5><pre>{JSON.stringify(selected.expected, null, 2)}</pre></section><section><h5>Actual · 실제결과</h5><pre>{JSON.stringify(selected.actual, null, 2)}</pre></section></div>
      <section className={`mismatch-panel ${selected.mismatches.length ? 'has-mismatch' : ''}`}><h5>Mismatch · 불일치 항목 <span className="count-chip">{selected.mismatches.length}</span></h5>{selected.mismatches.length ? <pre>{JSON.stringify(selected.mismatches, null, 2)}</pre> : <p>{selected.result==='ERROR'?'오류로 인해 업무 assertion 판정을 완료하지 못했습니다.':'불일치 항목이 없습니다.'}</p>}</section>
      <details><summary>실행 당시 관련 근거</summary><pre>{JSON.stringify({ apiSpecification: selected.apiSpecEvidence, references: selected.evidence, sources: selected.sourceEvidence }, null, 2)}</pre></details>
    </div>}
  </section>
}
