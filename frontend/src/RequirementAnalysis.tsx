import { useEffect, useRef, useState } from 'react'

type Fact = { text: string; chunkId: string }
type Evidence = { documentId: string; chunkId: string; documentType: string; section: string; contentSnippet: string; score: number }
type Analysis = {
  requirementId: string; confirmedConditions: Fact[]; ambiguousExpressions: string[]; missingConditions: string[];
  relatedBusinessRules: Fact[]; relatedApis: { api: string; chunkId: string }[];
  clarificationQuestions: string[]; evidence: Evidence[];
}

export default function RequirementAnalysis({ requirementId, onSaved }: { requirementId: string; onSaved: () => void }) {
  const [result, setResult] = useState<Analysis | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
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
      if (method === 'GET' && response.status === 404) { setNotice('저장된 분석이 없습니다. (HTTP 404)'); return }
      if (!response.ok) throw new Error(body?.message ?? `분석 요청에 실패했습니다. (HTTP ${response.status})`)
      if (!body || body.requirementId !== requirementId || !['confirmedConditions', 'ambiguousExpressions', 'missingConditions', 'relatedBusinessRules', 'relatedApis', 'clarificationQuestions', 'evidence'].every(key => Array.isArray(body[key]))) throw new Error('분석 응답 형식이 올바르지 않습니다.')
      setResult(body); setNotice('분석 조회에 성공했습니다.')
      if (method === 'POST') onSaved()
    } catch (err) {
      setError(err instanceof Error && err.name === 'AbortError'
        ? '응답 대기가 종료되었습니다. 저장 결과 조회로 완료 여부를 확인해 주세요.'
        : err instanceof Error ? err.message : '분석 요청에 실패했습니다.')
    } finally { clearTimeout(timer); setBusy(false); active.current = null }
  }
  const strings = (title: string, values: string[]) => <section><h4>{title}</h4>{values.length
    ? <ul>{values.map((text, i) => <li key={i}>{text}</li>)}</ul> : <p>해당 항목 없음</p>}</section>
  const facts = (title: string, values: Fact[]) => <section><h4>{title}</h4>{values.length
    ? <ul>{values.map((item, i) => <li key={i}>{item.text} <a href={`#evidence-${item.chunkId}`}>근거</a></li>)}</ul>
    : <p>확정 가능한 근거 없음</p>}</section>
  return <section className="analysis-panel" aria-label="요구사항 분석">
    <h3>근거 기반 요구사항 분석</h3>
    <p>검색 근거에서 확인된 문장과 추가 확인이 필요한 조건을 구분합니다.</p>
    <div className="analysis-actions">
      <button type="button" disabled={busy} onClick={() => request('POST')}>요구사항 분석</button>
      <button type="button" disabled={busy} onClick={() => request('GET')}>저장된 분석 조회</button>
    </div>
    {busy && <p role="status">분석 요청을 처리 중입니다. 로컬 모델 실행에는 수 분이 걸릴 수 있습니다.</p>}
    {error && <p role="alert" className="form-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {result && <div className="analysis-result">
      {facts('확인된 조건 · 근거 원문', result.confirmedConditions)}
      {strings('모호한 표현 · 확인 필요', result.ambiguousExpressions)}
      {strings('누락 또는 근거 부족 · 확인 필요', result.missingConditions)}
      {facts('관련 업무규칙 · 근거 원문', result.relatedBusinessRules)}
      <section><h4>관련 API</h4>{result.relatedApis.length ? <ul>{result.relatedApis.map((item, i) =>
        <li key={i}><code>{item.api}</code> <a href={`#evidence-${item.chunkId}`}>근거</a></li>)}</ul> : <p>확인된 API 없음</p>}</section>
      {strings('확인 질문', result.clarificationQuestions)}
      <section><h4>검색 근거 · Top-5</h4>{result.evidence.map(item => <article className="analysis-evidence" id={`evidence-${item.chunkId}`} key={item.chunkId}>
        <h5>{item.section}</h5><p>{item.documentType} · 유사도 {item.score.toFixed(4)}</p>
        <dl><dt>Document ID</dt><dd>{item.documentId}</dd><dt>Chunk ID</dt><dd>{item.chunkId}</dd></dl>
        <blockquote>{item.contentSnippet}</blockquote>
      </article>)}</section>
    </div>}
  </section>
}
