import Evaluations from './Evaluations'
import RequirementAnalysis from './RequirementAnalysis'
import TestCases from './TestCases'
import KnowledgeGraph from './KnowledgeGraph'
import { useState } from 'react'
import type { FormEvent } from 'react'

type Requirement = { id: string; title: string; description: string; status: string; createdAt: string }
type ApiError = { message?: string; fieldErrors?: Record<string, string> }

async function requestRequirement(url: string, options?: RequestInit): Promise<Requirement> {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(15000) })
  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({}))
    throw new Error(Object.values(error.fieldErrors ?? {}).join(' ') || error.message || '요청을 처리하지 못했습니다.')
  }
  return response.json()
}

function errorMessage(error: unknown) {
  if (error instanceof Error && ['TimeoutError', 'AbortError'].includes(error.name)) {
    return '응답 시간이 초과되었습니다. 등록 요청은 저장되었을 수 있으므로 중복 제출에 주의해 주세요.'
  }
  if (error instanceof TypeError) return '서버에 연결할 수 없습니다. 연결 상태를 확인해 주세요.'
  return error instanceof Error ? error.message : '요청을 처리하지 못했습니다.'
}

export default function Requirements() {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [lookupId, setLookupId] = useState('')
  const [result, setResult] = useState<Requirement | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    setError(''); setNotice(''); setResult(null)
    if (!title.trim() || !description.trim()) { setError('제목과 내용을 입력해 주세요.'); return }
    setBusy(true)
    try {
      const saved = await requestRequirement('/api/requirements', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description }),
      })
      setResult(saved); setLookupId(saved.id); setNotice('요구사항을 등록했습니다.')
      setTitle(''); setDescription('')
    } catch (err) { setError(errorMessage(err)) }
    finally { setBusy(false) }
  }

  async function loadRequirement(id: string) {
    if (busy) return
    setError(''); setNotice('')
    if (!id.trim()) { setError('조회할 ID를 입력해 주세요.'); return }
    setBusy(true)
    try {
      const saved = await requestRequirement(`/api/requirements/${encodeURIComponent(id.trim())}`)
      setResult(saved); setLookupId(saved.id); setNotice('저장된 요구사항을 조회했습니다.')
    } catch (err) { setResult(null); setError(errorMessage(err)) }
    finally { setBusy(false) }
  }

  async function lookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await loadRequirement(lookupId)
  }

  return (
    <section className="workspace requirements" aria-labelledby="requirement-title">
      <div className="section-heading">
        <div><p className="eyebrow">REQUIREMENTS</p><h2 id="requirement-title">요구사항 등록 · 조회</h2></div>
      </div>
      <form onSubmit={create} aria-label="요구사항 등록">
        <label htmlFor="requirement-title-input">제목 <span>(최대 200자)</span></label>
        <input id="requirement-title-input" value={title} onChange={e => setTitle(e.target.value)} required maxLength={200} disabled={busy} />
        <label htmlFor="requirement-description">내용 <span>(최대 10,000자)</span></label>
        <textarea id="requirement-description" value={description} onChange={e => setDescription(e.target.value)} required maxLength={10000} rows={6} disabled={busy} />
        <button type="submit" disabled={busy}>{busy ? '처리 중…' : '요구사항 저장'}</button>
      </form>
      <form onSubmit={lookup} className="lookup-form" aria-label="요구사항 조회">
        <label htmlFor="requirement-id">요구사항 ID</label>
        <div className="lookup-controls">
          <input id="requirement-id" value={lookupId} onChange={e => setLookupId(e.target.value)} required disabled={busy} placeholder="저장된 요구사항의 UUID" />
          <button type="submit" disabled={busy}>조회</button>
        </div>
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      <p className="form-notice" role="status">{notice}</p>
      {result && <article className="requirement-result" aria-label="요구사항 상세">
        <h3>{result.title}</h3>
        <dl><dt>ID</dt><dd>{result.id}</dd><dt>상태</dt><dd>{result.status}</dd>
          <dt>등록 일시</dt><dd>{new Date(result.createdAt).toLocaleString('ko-KR')}</dd></dl>
        <p className="requirement-description">{result.description}</p>
      </article>}
      {result && <RequirementAnalysis key={`RequirementAnalysis:${result.id}`} requirementId={result.id} onSaved={() => setResult(current => current && current.status === 'DRAFT' ? { ...current, status: 'ANALYZED' } : current)} />}
      {result && <TestCases key={`TestCases:${result.id}`} requirementId={result.id} />}
      <Evaluations key={`Evaluations:${result?.id ?? "none"}`} requirementId={result?.id ?? ""} requirementBusy={busy} onSelectRequirement={loadRequirement} />
      {result && <KnowledgeGraph key={`KnowledgeGraph:${result.id}`} requirementId={result.id} />}
    </section>
  )
}
