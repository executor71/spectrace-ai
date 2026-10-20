import GettingStarted, { exampleRequest } from './GettingStarted'
import './onboarding.css'
import Dashboard, { ExportButton } from './Dashboard'
import './dashboard.css'
import Evaluations from './Evaluations'
import RequirementAnalysis from './RequirementAnalysis'
import TestCases from './TestCases'
import KnowledgeGraph from './KnowledgeGraph'
import { useEffect, useState } from 'react'
import Icon from './Icon'
import type { Screen } from './navigation'
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

export default function Requirements({ view, onNavigate, onAnalysisBusy }: { view: Screen; onNavigate: (view: Screen) => void; onAnalysisBusy: (busy: boolean) => void }) {
  const [targetTc, setTargetTc] = useState('')
  async function selectFromDashboard(id: string, next: Screen, tc = '') {
    const loaded = await loadRequirement(id)
    if (loaded) { setTargetTc(tc); onNavigate(next) }
  }
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [lookupId, setLookupId] = useState('')
  const [result, setResult] = useState<Requirement | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  const [toast, setToast] = useState('')
  const [analysisSummary, setAnalysisSummary] = useState<{ conditions: number; evidence: number } | null>(null)
  const [testSummary, setTestSummary] = useState<{ total: number; approved: number } | null>(null)
  useEffect(() => { setAnalysisSummary(null); setTestSummary(null) }, [result?.id])
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(''), 6000)
    return () => clearTimeout(timer)
  }, [toast])

  function loadExample() {
    if (busy) return
    setTitle(exampleRequest.title); setDescription(exampleRequest.description)
    setError(''); setNotice('예제를 입력폼에 불러왔습니다. 아직 저장되지 않았습니다. 내용을 확인한 뒤 변경 요청 저장을 눌러 주세요.')
    onNavigate('requirements')
  }
  const nextStep: Screen = !result ? 'requirements' : !analysisSummary ? 'analysis' : !testSummary?.total ? 'testcases' : testSummary.approved ? 'execution' : 'review'
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
      setTitle(''); setDescription(''); setToast('요구사항이 등록되었습니다.')
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
      setResult(saved); setLookupId(saved.id); setNotice('저장된 요구사항을 조회했습니다.'); return true
    } catch (err) { setError(errorMessage(err)); return false }
    finally { setBusy(false) }
  }

  async function lookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await loadRequirement(lookupId)
  }
  const needsRequirement = !result && ['analysis', 'testcases', 'review', 'execution', 'graph'].includes(view)
  return <div className="requirements">
    {view === 'dashboard' && <GettingStarted onExample={loadExample} onNavigate={onNavigate} next={nextStep} selectedTitle={result?.title} disabled={busy} />}
    <section hidden={view === 'dashboard' && !result} className="context-bar" aria-label="현재 요구사항">
      <div className="context-identity"><span className="context-icon"><Icon name="requirements" /></span><div><small>현재 요구사항</small><strong>{result?.title ?? '선택된 요구사항이 없습니다'}</strong>{result && <span className={`status-badge status-${result.status}`}>{result.status}</span>}</div></div>
      <form onSubmit={lookup} className="lookup-form" aria-label="요구사항 조회"><label htmlFor="requirement-id" className="sr-only">요구사항 ID</label><div className="lookup-controls"><input id="requirement-id" value={lookupId} onChange={e => setLookupId(e.target.value)} required disabled={busy} placeholder="저장된 요청 ID로 조회" /><button type="submit" className="secondary" disabled={busy}>{busy ? '조회 중…' : '조회'}</button></div></form>
    </section>
    {result && <p className="metadata">선택 상태: {result.status} · 조회한 분석 조건 {analysisSummary?.conditions ?? '—'}건 · 조회한 TC {testSummary?.total ?? '—'}건</p>}
    {result && <nav className="p13-context-actions" aria-label="요구사항 상세 탐색">{(['requirements','analysis','testcases','review','execution','evaluation','graph'] as const).map((next,i) => <button key={next} className="secondary" onClick={() => onNavigate(next)}>{['상세','변경 요청 분석','테스트 자동 생성','테스트 검토·승인','테스트 실행·결과 확인','기술 검증','변경 영향 관계 확인'][i]}</button>)}<ExportButton id={result.id}/></nav>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <p className="form-notice" role="status">{notice}</p>
    <div hidden={view !== 'dashboard'}><Dashboard onSelect={selectFromDashboard} onNavigate={onNavigate} /></div>
    <div hidden={view !== 'requirements'} className="requirement-layout">
      <section className="card requirement-form-card"><div className="card-heading"><div><p className="eyebrow">NEW REQUIREMENT</p><h2>새 변경 요청 입력</h2></div><Icon name="requirements" /></div><div className="example-form-guide"><p>입력이 처음이라면 합성 IT 자산관리 예제를 사용해 보세요.</p><button type="button" className="secondary" disabled={busy} onClick={loadExample}>예제 불러오기</button><small>입력폼만 채우며 저장·AI 분석·테스트 실행은 자동으로 수행하지 않습니다.</small></div><form onSubmit={create} aria-label="변경 요청 등록"><label htmlFor="requirement-title-input">제목 <span>최대 200자</span></label><input id="requirement-title-input" value={title} onChange={e => setTitle(e.target.value)} required maxLength={200} disabled={busy} placeholder="예: 대여 승인 권한 검증" /><div className="label-row"><label htmlFor="requirement-description">상세 내용</label><span>{description.length.toLocaleString()} / 10,000</span></div><textarea id="requirement-description" value={description} onChange={e => setDescription(e.target.value)} required maxLength={10000} rows={9} disabled={busy} placeholder="업무의 목적과 조건, 예외 상황을 구체적으로 작성해 주세요." /><p className="field-hint">명확한 업무조건은 분석과 테스트의 출발점이 됩니다.</p><div className="form-footer"><span>저장 → 변경 요청 분석 → 테스트 생성 순서로 진행합니다.</span><button type="submit" disabled={busy}>{busy ? <><span className="spinner" /> 저장 중…</> : '변경 요청 저장'}</button></div></form></section>
      <section className="card requirement-summary"><p className="eyebrow">REQUIREMENT DETAILS</p>{result ? <article className="requirement-result" aria-label="요구사항 상세"><span className={`status-badge status-${result.status}`}>{result.status}</span><h3>{result.title}</h3><p className="requirement-description">{result.description}</p><dl><dt>등록 일시</dt><dd>{new Date(result.createdAt).toLocaleString('ko-KR')}</dd><dt>요청 ID</dt><dd><code>{result.id}</code></dd></dl><button onClick={() => onNavigate('analysis')}>다음: 변경 요청 분석 <Icon name="arrow" size={17} /></button></article> : <div className="empty-state"><Icon name="requirements" size={34} /><h3>아직 저장한 변경 요청이 없습니다</h3><p>왼쪽에 변경 요청을 입력하거나 예제를 불러온 뒤 저장하세요. 저장 후 분석을 직접 시작할 수 있습니다.</p></div>}</section>
    </div>
    {needsRequirement && <section className="card empty-state"><span className="empty-icon"><Icon name="requirements" size={28} /></span><h2>먼저 요구사항을 선택해 주세요</h2><p>대시보드 목록에서 저장된 요청을 선택하거나, 변경 요청 입력에서 예제를 불러와 저장하세요.</p><button onClick={() => onNavigate('requirements')}>변경 요청 입력로 이동 <Icon name="arrow" size={16} /></button><button className="text-button" onClick={() => onNavigate('evaluation')}>기술 검증 예제 찾아보기</button></section>}
    <div hidden={view !== 'analysis'}>{result && <RequirementAnalysis key={`analysis:${result.id}`} requirementId={result.id} onBusyChange={onAnalysisBusy} onSummary={setAnalysisSummary} onNavigate={onNavigate} onSaved={() => setResult(current => current && current.status === 'DRAFT' ? { ...current, status: 'ANALYZED' } : current)} />}</div>
    <div hidden={!['testcases', 'review', 'execution'].includes(view)}>{result && <TestCases key={`tests:${result.id}`} requirementId={result.id} initialTc={targetTc} view={view} onNavigate={onNavigate} onSummary={setTestSummary} />}</div>
    <div hidden={view !== 'evaluation'}><Evaluations key={`evaluation:${result?.id ?? 'none'}`} requirementId={result?.id ?? ''} requirementBusy={busy} onSelectRequirement={async id => { await loadRequirement(id) }} /></div>
    <div hidden={view !== 'graph'}>{result && <KnowledgeGraph key={`graph:${result.id}`} requirementId={result.id} />}</div>
    {toast && <div className="toast" role="status"><span className="toast-icon"><Icon name="check" /></span><div><strong>등록 완료</strong><span>{toast}</span></div><button className="icon-button" aria-label="알림 닫기" onClick={() => setToast('')}><Icon name="close" size={17} /></button></div>}
  </div>
}
