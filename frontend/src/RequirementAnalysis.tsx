import type { Screen } from './navigation'
import { useEffect, useRef, useState } from 'react'

type Fact = { text: string; chunkId: string }
type Evidence = { documentId: string; chunkId: string; documentType: string; section: string; contentSnippet: string; score: number }
type Analysis = {
  requirementId: string; confirmedConditions: Fact[]; ambiguousExpressions: string[]; missingConditions: string[];
  relatedBusinessRules: Fact[]; relatedApis: { api: string; chunkId: string }[];
  clarificationQuestions: string[]; evidence: Evidence[];
}

export default function RequirementAnalysis({ requirementId, onSaved, onBusyChange, onSummary, onNavigate }: { onNavigate: (screen: Screen) => void; requirementId: string; onSaved: () => void; onBusyChange: (busy: boolean) => void; onSummary: (value: { conditions: number; evidence: number }) => void }) {
  const [result, setResult] = useState<Analysis | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    onBusyChange(busy)
    if (!busy) return
    setElapsed(0)
    const start = Date.now()
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [busy, onBusyChange])
  useEffect(() => () => onBusyChange(false), [onBusyChange])
  const active = useRef<AbortController | null>(null)
  useEffect(() => () => active.current?.abort(), [])

  async function request(method: 'POST' | 'GET') {
    if (busy) return
    setBusy(true); setError(''); setNotice(''); setResult(null)
    const controller = new AbortController(); active.current = controller
    const timer = setTimeout(() => controller.abort(), 660000)
    try {
      const response = await fetch(`/api/requirements/${encodeURIComponent(requirementId)}/analysis`, { method, signal: controller.signal })
      const body = await response.json().catch(() => null)
      if (method === 'GET' && response.status === 404) { setNotice('AI 분석 결과가 아직 없습니다. 변경 요청을 저장한 것만으로는 분석되지 않습니다. ‘변경 요청 분석 시작’을 눌러 관련 업무규칙을 확인하세요.'); return }
      if (response.status === 429 && body?.code === 'ANALYSIS_BUSY') throw new Error('다른 분석이 진행 중이라 새 분석을 시작하지 못했습니다. 진행 중인 분석이 끝난 뒤 ‘변경 요청 분석 시작’을 다시 누르거나 ‘저장된 분석 조회’로 완료 여부를 확인하세요.')
      if (!response.ok) throw new Error(body?.message ?? `분석 요청에 실패했습니다. (HTTP ${response.status})`)
      if (!body || body.requirementId !== requirementId || !['confirmedConditions', 'ambiguousExpressions', 'missingConditions', 'relatedBusinessRules', 'relatedApis', 'clarificationQuestions', 'evidence'].every(key => Array.isArray(body[key]))) throw new Error('분석 응답 형식이 올바르지 않습니다.')
      setResult(body); onSummary({ conditions: body.confirmedConditions.length, evidence: body.evidence.length }); setNotice(method === 'GET' ? '저장된 분석을 불러왔습니다.' : '변경 요청 분석을 완료했습니다. 확인된 조건과 질문을 읽은 뒤 테스트 자동 생성으로 진행하세요.')
      if (method === 'POST') onSaved()
    } catch (err) {
      setError(err instanceof Error && err.name === 'AbortError'
        ? '응답 대기가 종료되었습니다. 저장 결과 조회로 완료 여부를 확인해 주세요.'
        : err instanceof Error ? err.message : '분석 요청에 실패했습니다.')
    } finally { clearTimeout(timer); setBusy(false); active.current = null }
  }
  const strings = (title: string, values: string[]) => <section className="card analysis-card"><h4>{title}</h4>{values.length
    ? <ul>{values.map((text, i) => <li key={i}>{text}</li>)}</ul> : <p>해당 항목 없음</p>}</section>
  const facts = (title: string, values: Fact[]) => <section className="card analysis-card"><h4>{title}</h4>{values.length
    ? <ul>{values.map((item, i) => <li key={i}>{item.text} <a href={`#evidence-${item.chunkId}`}>근거</a></li>)}</ul>
    : <p>확정 가능한 근거 없음</p>}</section>
  return <section className="analysis-panel" aria-busy={busy} aria-label="변경 요청 분석">
    <div className="panel-title"><span className="eyebrow">EVIDENCE-BASED ANALYSIS</span><h2>변경 요청 분석</h2></div>
    <p>검색 근거에서 확인된 문장과 추가 확인이 필요한 조건을 구분합니다.</p>
    <div className="analysis-actions">
      <button type="button" disabled={busy} onClick={() => request('POST')}>변경 요청 분석 시작</button>
      <button type="button" className="secondary" disabled={busy} onClick={() => request('GET')}>저장된 분석 조회</button>
    </div>
    {busy && <div className="loading-panel" role="status"><span className="spinner" /><div><strong>관련 업무규칙을 찾아 AI가 분석하고 있습니다</strong><p>경과시간 {Math.floor(elapsed / 60)}분 {elapsed % 60}초 · 로컬 모델 분석에는 수 분이 걸릴 수 있습니다.</p><small>중복 요청하지 않고 기다려 주세요. 다른 화면으로 이동해도 분석은 계속되며, 돌아와 결과를 확인할 수 있습니다.</small></div></div>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!result && !busy && !notice && !error && <div className="card empty-state"><h3>AI 분석 결과를 먼저 확인하세요</h3><p>아직 이 화면에 분석을 불러오지 않았습니다. 처음이면 ‘변경 요청 분석 시작’, 이전에 분석했다면 ‘저장된 분석 조회’를 누르세요.</p></div>}
    {result && <div className="guide-next"><p>확인된 조건과 확인 질문을 검토한 뒤 테스트를 생성하세요.</p><button onClick={() => onNavigate('testcases')}>다음: 테스트 자동 생성</button></div>}
    {result && <div className="analysis-result">
      {facts('확인된 업무조건', result.confirmedConditions)}
      {strings('모호한 표현', result.ambiguousExpressions)}
      {strings('누락 의심 조건', result.missingConditions)}
      {facts('관련 업무규칙 · 근거 원문', result.relatedBusinessRules)}
      <section className="card analysis-card"><h4>관련 API</h4>{result.relatedApis.length ? <ul>{result.relatedApis.map((item, i) =>
        <li key={i}><code>{item.api}</code> <a href={`#evidence-${item.chunkId}`}>근거</a></li>)}</ul> : <p>확인된 API 없음</p>}</section>
      {strings('확인 질문', result.clarificationQuestions)}
      <section className="card evidence-section"><div className="card-heading"><h4>분석에 사용한 업무규칙과 근거 자료</h4><span className="count-chip">Top-{result.evidence.length}</span></div>{result.evidence.map(item => <article className="analysis-evidence" id={`evidence-${item.chunkId}`} key={item.chunkId}>
        <h5>{item.section}</h5><p>{item.documentType} · 유사도 {item.score.toFixed(4)}</p>
        <dl><dt>Document ID</dt><dd>{item.documentId}</dd><dt>Chunk ID</dt><dd>{item.chunkId}</dd></dl>
        <blockquote>{item.contentSnippet}</blockquote>
      </article>)}</section>
    </div>}
  </section>
}
