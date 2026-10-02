import { useState } from 'react'

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

export default function Evaluations({ requirementId }: { requirementId: string }) {
  const [runs, setRuns] = useState<Evaluation[]>([])
  const [selected, setSelected] = useState<Evaluation | null>(null)
  const [mode, setMode] = useState('GENERATED')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function request(create: boolean) {
    if (busy) return
    setBusy(true); setError('')
    try {
      const response = await fetch(create ? '/api/evaluations' : `/api/requirements/${encodeURIComponent(requirementId)}/evaluations`, {
        method: create ? 'POST' : 'GET', headers: { 'Content-Type': 'application/json' },
        ...(create ? { body: JSON.stringify({ requirementId, datasetVersion: 'phase6-v1', contentMode: mode }) } : {}), signal: AbortSignal.timeout(90000),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.message || body.detail || '평가 요청에 실패했습니다.')
      if (create) { setRuns(previous => [body, ...previous]); setSelected(body) }
      else { setRuns(body); setSelected(body[0] ?? null) }
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
    <h2 id="evaluations-title">Ground Truth 평가</h2>
    <p>고정된 평가셋에 등록된 요구사항만 평가합니다. 검색 Top-5와 저장된 테스트를 비교하며 분석·생성을 다시 호출하지 않습니다.</p>
    <label htmlFor="evaluation-mode">평가할 내용</label>
    <select id="evaluation-mode" value={mode} disabled={busy} onChange={e => setMode(e.target.value)}><option value="GENERATED">AI 생성 원본</option><option value="REVIEWED">사용자 검토 현재값</option></select>
    <div className="lookup-controls"><button disabled={busy} onClick={() => request(true)}>평가 실행</button><button disabled={busy} onClick={() => request(false)}>저장된 평가 조회</button></div>
    {busy && <p role="status">평가 처리 중…</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    <ul className="evaluation-history">{runs.map(run => <li key={run.id}><button disabled={busy} aria-pressed={selected?.id === run.id} onClick={() => select(run.id)}>{new Date(run.createdAt).toLocaleString('ko-KR')} · {run.dataset.split} · {run.contentMode} · {run.status}</button></li>)}</ul>
    {selected && <article className="evaluation-result" aria-label="평가 결과">
      <h3>{selected.dataset.split} · {selected.dataset.caseId}</h3>
      <p>상태: {selected.status} · 평가 대상: {selected.contentMode} · 기준: {selected.metricVersion}</p>
      <p>평가 ID: {selected.id}</p>
      {selected.issues.length > 0 && <ul aria-label="평가 주의 사항">{selected.issues.map((issue, i) => <li key={i}>{typeof issue === 'string' ? issue : issue.message}</li>)}</ul>}
      {metrics && <>
        <table className="evaluation-kpis"><thead><tr><th>KPI</th><th>측정값 (분자/분모)</th></tr></thead><tbody>
          <tr><th>Recall@5</th><td>{percentage(metrics.recallAt5)}</td></tr>
          <tr><th>Test Scenario Coverage</th><td>{percentage(metrics.scenarioCoverage)}</td></tr>
          <tr><th>TestCase Validity (코드 판정)</th><td>{percentage(metrics.testCaseValidity)}</td></tr>
        </tbody></table>
        <p>평가 대상: 검색 {metrics.counts.queries}건 · TC {metrics.counts.testCases}개 · 필수 시나리오 {metrics.counts.requiredScenarios}개 · 정답 문서 {metrics.counts.expectedDocuments}개</p>
        <p>Validity 실패 {metrics.testCaseValidity.failedCount}개 · 자동 미판정 {metrics.testCaseValidity.unknownCount}개. 자유 서술의 의미적 모순은 미평가이며 deterministic 점수에 혼합하지 않습니다. TC가 없으면 Validity는 N/A입니다.</p>
        <h4>누락된 Ground Truth 시나리오</h4>
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
