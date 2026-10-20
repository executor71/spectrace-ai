import { TechnicalGuide } from './GettingStarted'
import { useEffect, useState } from 'react'

type EvaluationTarget = { requirementId: string; datasetVersion: string; caseId: string; split: string }
type Ratio = { numerator: number; denominator: number; value: number | null; status: string }
type Scenario = { scenarioId: string; category: string; description: string; covered: boolean; matchedTestCaseIds: string[] }
type Evaluation = {
  id: string; createdAt: string; status: string; contentMode: string; metricVersion: string; inputHash?: string;
  dataset: { datasetVersion: string; split: string; caseId: string; groundTruthHash: string };
  issues: (string | { code: string; message: string })[];
  metrics: null | {
    recallAt5: Ratio & { missingDocumentIds: string[]; retrievedChunkCount: number };
    scenarioCoverage: Ratio & { missingScenarios: Scenario[]; scenarios: Scenario[] };
    testCaseValidity: Ratio & { failedCount: number; unknownCount: number; cases: { testCaseId: string; status: string; checks: Record<string, string>; consistencyReasons: string[] }[] };
    counts: { queries: number; testCases: number; requiredScenarios: number; expectedDocuments: number };
  };
}
const percentage = (m: Ratio) => m.value === null ? `N/A (${m.numerator}/${m.denominator})` : `${(m.value * 100).toFixed(1)}% (${m.numerator}/${m.denominator})`

export default function Evaluations({ requirementId, requirementBusy, onSelectRequirement }: { requirementId: string; requirementBusy: boolean; onSelectRequirement: (id: string) => Promise<void> }) {
  const [loaded,setLoaded] = useState(false)
  useEffect(() => { setLoaded(false); setRuns([]); setSelected(null) }, [requirementId])
  const [runs, setRuns] = useState<Evaluation[]>([])
  const [selected, setSelected] = useState<Evaluation | null>(null)
  const [mode, setMode] = useState('GENERATED')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [targets, setTargets] = useState<EvaluationTarget[] | null>(null)
  const [targetsError, setTargetsError] = useState('')
  const [targetsAttempt, setTargetsAttempt] = useState(0)
  const [sampleId, setSampleId] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    setTargets(null); setTargetsError('')
    async function loadTargets() {
      try {
        const response = await fetch('/api/evaluations/targets', { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) })
        const body = await response.json().catch(() => null)
        if (!response.ok) throw new Error(body?.message || body?.detail || '평가 대상 목록을 불러오지 못했습니다.')
        if (body?.datasetVersion !== 'phase6-v1' || !Array.isArray(body.requirements) || !body.requirements.every((target: EvaluationTarget) => typeof target.requirementId === 'string' && target.datasetVersion === body.datasetVersion && typeof target.caseId === 'string' && typeof target.split === 'string')) throw new Error('평가 대상 목록의 응답 형식이 올바르지 않습니다.')
        if (!controller.signal.aborted) setTargets(body.requirements)
      } catch (err) {
        if (!controller.signal.aborted) setTargetsError(err instanceof Error ? err.message : '평가 대상 조회에 실패했습니다.')
      }
    }
    void loadTargets()
    return () => controller.abort()
  }, [targetsAttempt])
  const target = targets?.find(item => item.requirementId === requirementId)
  const eligible = !!target
  async function loadSample() {
    if (!sampleId || busy || requirementBusy) return
    setBusy(true)
    try { await onSelectRequirement(sampleId) }
    finally { setBusy(false) }
  }
  async function request(create: boolean) {
    if (busy || requirementBusy || !requirementId || (create && !eligible)) return
    setBusy(true); setError('')
    try {
      const response = await fetch(create ? '/api/evaluations' : `/api/requirements/${encodeURIComponent(requirementId)}/evaluations`, {
        method: create ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' },
        ...(create ? { body: JSON.stringify({ requirementId, datasetVersion: 'phase6-v1', contentMode: mode }) } : {}), signal: AbortSignal.timeout(90000),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.message || body.detail || '평가 요청에 실패했습니다.')
      if (create) { setRuns(previous => [body, ...previous]); setSelected(body) }
      else { setRuns(body); setSelected(body[0] ?? null); setLoaded(true) }
    } catch (err) { setError(err instanceof Error ? err.message : '평가 요청에 실패했습니다.') }
    finally { setBusy(false) }
  }
  async function select(id: string) {
    setBusy(true); setError('')
    try {
      const response = await fetch(`/api/evaluations/${encodeURIComponent(id)}`, { signal: AbortSignal.timeout(15000) })
      if (!response.ok) throw new Error('저장된 평가 조회에 실패했습니다.')
      setSelected(await response.json())
    } catch (err) { setError(err instanceof Error ? err.message : '조회 실패') }
    finally { setBusy(false) }
  }
  const metrics = selected?.metrics
  return <section className="evaluations" aria-labelledby="evaluations-title">
    <div className="panel-title"><span className="eyebrow">기술 검증</span><h2 id="evaluations-title">기술 검증·관리</h2></div>
    <p>고정된 평가셋에 등록된 요구사항만 평가합니다. 검색 Top-5와 저장된 테스트를 비교하며 분석·생성을 다시 호출하지 않습니다.</p>
    <TechnicalGuide />
    <div className="card evaluation-controls"><label htmlFor="evaluation-sample">등록된 품질 검증 예제</label>
    <div className="lookup-controls">
      <select id="evaluation-sample" value={sampleId} disabled={busy || requirementBusy || !targets?.length} onChange={e => setSampleId(e.target.value)}>
        <option value="">등록된 샘플을 선택하세요</option>
        {targets?.map(item => <option key={item.requirementId} value={item.requirementId}>{item.caseId} · {item.split} · {item.requirementId}</option>)}
      </select>
      <button type="button" disabled={busy || requirementBusy || !sampleId} onClick={loadSample}>샘플 요구사항 조회</button>
    </div>
    <p>샘플을 조회하면 해당 요구사항으로 전환됩니다. 정답이나 평가셋 연결은 변경하지 않습니다.</p>
    {targetsError ? <div role="alert" className="form-error">평가 대상 등록 여부를 확인하지 못했습니다. {targetsError} <button type="button" onClick={() => setTargetsAttempt(value => value + 1)}>평가 대상 다시 확인</button></div>
      : targets === null ? <p role="status">평가 대상 등록 여부를 확인 중입니다.</p>
      : !requirementId ? <p role="status">요구사항을 조회하거나 등록된 평가 샘플을 선택해 주세요.</p>
      : !eligible ? <p role="status">평가셋 미등록: 이 변경 요청은 고정된 품질 검증 예제에 연결되지 않아 점수를 계산할 수 없습니다. 일반 테스트 검토·승인과 실행은 계속 사용할 수 있습니다. 점수 비교가 필요하면 위에서 등록된 품질 검증 예제를 선택해 주세요.</p>
      : <p role="status">정량평가 대상: {target.caseId} · {target.split} · {target.datasetVersion}</p>}
    {targets?.length === 0 && <p>등록된 평가 샘플이 없습니다.</p>}
    <label htmlFor="evaluation-mode">평가할 내용</label>
    <select id="evaluation-mode" value={mode} disabled={busy || requirementBusy || !eligible} onChange={e => setMode(e.target.value)}><option value="GENERATED">AI 생성 원본</option><option value="REVIEWED">사용자 검토 현재값</option></select>
    <div className="lookup-controls"><button type="button" disabled={busy || requirementBusy || !eligible} onClick={() => request(true)}>평가 실행</button><button type="button" className="secondary" disabled={busy || requirementBusy || !requirementId} onClick={() => request(false)}>저장된 평가 조회</button></div>
    </div>{busy && <p role="status" className="loading-panel"><span className="spinner" /> 평가 처리 중…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {eligible && loaded && !runs.length && !busy && !error && <p role="status">미평가: 등록된 예제지만 저장된 평가 결과가 없습니다. 평가할 내용의 원본·검토본을 선택한 뒤 ‘평가 실행’을 눌러 주세요.</p>}
    <ul className="evaluation-history">{runs.map(run => <li key={run.id}><button disabled={busy} aria-pressed={selected?.id === run.id} onClick={() => select(run.id)}>{new Date(run.createdAt).toLocaleString('ko-KR')} · {run.dataset.split} · {run.contentMode} · {run.status}</button></li>)}</ul>
    {selected && <article className="card evaluation-result" aria-label="평가 결과">
      <h3>{selected.dataset.split} · {selected.dataset.caseId}</h3>
      <p>상태: {selected.status} · 평가 대상: {selected.contentMode} · 기준: {selected.metricVersion}</p>
      <p>평가 ID: {selected.id}</p>
      {selected.issues.length > 0 && <ul aria-label="평가 주의 사항">{selected.issues.map((issue, i) => <li key={i}>{typeof issue === 'string' ? issue : issue.message}</li>)}</ul>}
      {metrics && <>
        <div className="evaluation-metric-grid">{[{ name: 'Recall@5', value: metrics.recallAt5, hint: '검색 문서 재현율' }, { name: 'TestCase Coverage', value: metrics.scenarioCoverage, hint: '필수 시나리오 커버리지' }, { name: 'Validity', value: metrics.testCaseValidity, hint: '코드로 판정한 테스트 유효성' }].map(item => <article key={item.name} className="metric-card"><p>{item.name}</p><strong>{item.value.value === null ? 'N/A' : `${(item.value.value * 100).toFixed(1)}%`}</strong><small>{item.value.numerator} / {item.value.denominator} · {item.hint}</small></article>)}</div><div className="table-scroll" role="region" aria-label="평가 KPI 상세" tabIndex={0}>
        <table className="evaluation-kpis"><thead><tr><th>KPI</th><th>측정값 (분자/분모)</th></tr></thead><tbody>
          <tr><th>Recall@5</th><td>{percentage(metrics.recallAt5)}</td></tr>
          <tr><th>Test Scenario Coverage</th><td>{percentage(metrics.scenarioCoverage)}</td></tr>
          <tr><th>TestCase Validity (코드 판정)</th><td>{percentage(metrics.testCaseValidity)}</td></tr>
        </tbody></table></div>
        <p>평가 대상: 검색 {metrics.counts.queries}건 · TC {metrics.counts.testCases}개 · 필수 시나리오 {metrics.counts.requiredScenarios}개 · 정답 문서 {metrics.counts.expectedDocuments}개</p>
        <p>Validity 실패 {metrics.testCaseValidity.failedCount}개 · 자동 미판정 {metrics.testCaseValidity.unknownCount}개. 자유 서술의 의미적 모순은 미평가이며 deterministic 점수에 혼합하지 않습니다. TC가 없으면 Validity는 N/A입니다.</p>
        <h4>기준 대비 누락된 시나리오</h4>
        <ul className="evaluation-missing-scenarios">{metrics.scenarioCoverage.missingScenarios.map(s => <li key={s.scenarioId}>{s.scenarioId} · {s.category} · {s.description}</li>)}</ul>
        {!metrics.scenarioCoverage.missingScenarios.length && <p>필수 시나리오 누락 없음</p>}
        <h4>검색 실패 문서</h4>
        <ul className="evaluation-missing-documents">{metrics.recallAt5.missingDocumentIds.map(id => <li key={id}>{id}</li>)}</ul>
        {!metrics.recallAt5.missingDocumentIds.length && <p>검색 실패 문서 없음</p>}
        <details><summary>TC별 validity checklist</summary>{metrics.testCaseValidity.cases.map(tc => <div key={tc.testCaseId}><p>{tc.testCaseId} · {tc.status}</p><ul>{Object.entries(tc.checks).map(([key, value]) => <li key={key}>{key}: {value}</li>)}</ul><p>{tc.consistencyReasons.join(', ')}</p></div>)}</details>
        <details><summary>시나리오별 매칭 결과</summary><ul>{metrics.scenarioCoverage.scenarios.map(s => <li key={s.scenarioId}>{s.scenarioId}: {s.covered ? s.matchedTestCaseIds.join(', ') : '누락'}</li>)}</ul></details>
      </>}
      <details><summary>재현성 정보</summary><p>Dataset: {selected.dataset.datasetVersion}</p><p>Ground Truth hash: {selected.dataset.groundTruthHash}</p><p>Input hash: {selected.inputHash ?? '입력 수집 실패'}</p></details>
    </article>}
  </section>
}
