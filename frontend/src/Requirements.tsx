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
      setResult(saved); setLookupId(saved.id); setNotice('저장된 요구사항을 조회했습니다.')
    } catch (err) { setResult(null); setError(errorMessage(err)) }
    finally { setBusy(false) }
  }

  async function lookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await loadRequirement(lookupId)
  }
  const needsRequirement = !result && ['analysis', 'testcases', 'review', 'execution', 'graph'].includes(view)
  return <div className="requirements">
    <section className="context-bar" aria-label="현재 요구사항">
      <div className="context-identity"><span className="context-icon"><Icon name="requirements" /></span><div><small>현재 요구사항</small><strong>{result?.title ?? '선택된 요구사항이 없습니다'}</strong>{result && <span className={`status-badge status-${result.status}`}>{result.status}</span>}</div></div>
      <form onSubmit={lookup} className="lookup-form" aria-label="요구사항 조회"><label htmlFor="requirement-id" className="sr-only">요구사항 ID</label><div className="lookup-controls"><input id="requirement-id" value={lookupId} onChange={e => setLookupId(e.target.value)} required disabled={busy} placeholder="Requirement ID로 조회" /><button type="submit" className="secondary" disabled={busy}>{busy ? '조회 중…' : '조회'}</button></div></form>
    </section>
    {error && <p className="form-error" role="alert">{error}</p>}
    <p className="form-notice" role="status">{notice}</p>
    <div hidden={view !== 'dashboard'} className="dashboard-view">
      <section className="welcome-card"><div><span className="eyebrow">FROM REQUIREMENTS TO CONFIDENCE</span><h2>모든 검증에,<br />명확한 근거를.</h2><p>요구사항을 분석하고, 테스트를 검토하고,<br className="desktop-break" /> 실행 결과까지 하나의 흐름으로 연결하세요.</p><button onClick={() => onNavigate('requirements')}>요구사항 관리 <Icon name="arrow" size={17} /></button></div><div className="welcome-diagram" aria-label="요구사항에서 검증까지"><span className="diagram-caption">TRACEABLE BY DESIGN</span><div><span><Icon name="requirements" />요구사항</span><i>→</i><span><Icon name="analysis" />AI 분석</span></div><div className="diagram-connector">↓</div><div><span><Icon name="execution" />검증 결과</span><i>←</i><span><Icon name="testcases" />테스트케이스</span></div><small><span className="live-dot" /> Evidence로 연결된 검증 과정</small></div></section>
      <div className="metric-grid"><article className="metric-card"><span className="metric-icon"><Icon name="requirements" /></span><p>선택한 요구사항</p><strong>{result ? '1' : '—'}</strong><small>{result ? result.status : '요구사항을 조회해 시작하세요'}</small></article><article className="metric-card"><span className="metric-icon blue"><Icon name="analysis" /></span><p>검색된 Evidence</p><strong>{analysisSummary?.evidence ?? '—'}<small>건</small></strong><small>{analysisSummary ? `확인된 조건 ${analysisSummary.conditions}건` : '저장된 분석 조회 후 표시'}</small></article><article className="metric-card"><span className="metric-icon violet"><Icon name="testcases" /></span><p>테스트케이스</p><strong>{testSummary?.total ?? '—'}<small>건</small></strong><small>현재 요구사항의 저장된 테스트</small></article><article className="metric-card"><span className="metric-icon amber"><Icon name="review" /></span><p>승인된 테스트</p><strong>{testSummary?.approved ?? '—'}<small>건</small></strong><small>서버의 승인 상태 기준</small></article></div>
      <div className="dashboard-columns"><section className="card workflow-card"><div className="card-heading"><div><p className="eyebrow">YOUR WORKFLOW</p><h3>검증 워크플로</h3></div><span className="subtle-label">4 STEPS</span></div>{([{ id: 'analysis', name: '요구사항 분석', text: '확정 조건과 원문 Evidence 확인' }, { id: 'testcases', name: '테스트케이스', text: '유형별 시나리오와 기대결과 확인' }, { id: 'review', name: '검토 및 승인', text: '사람의 판단으로 테스트 품질 보완' }, { id: 'execution', name: '실행 및 검증', text: '승인된 테스트의 실제 결과 비교' }] as const).map((item, i) => <button className="workflow-row" key={item.id} onClick={() => onNavigate(item.id)}><span className="step-number">0{i + 1}</span><span><strong>{item.name}</strong><small>{item.text}</small></span><Icon name="arrow" size={17} /></button>)}</section><div className="insight-stack"><section className="card selected-card"><p className="eyebrow">CURRENT CONTEXT</p><h3>{result?.title ?? '첫 번째 요구사항을 선택하세요'}</h3><p>{result ? '선택한 요구사항은 모든 작업 화면에서 동일하게 유지됩니다.' : '상단에서 저장된 ID를 조회하거나 새로운 요구사항을 등록하세요.'}</p><button className="secondary" onClick={() => onNavigate('requirements')}>{result ? '요구사항 상세 보기' : '요구사항 등록하기'} <Icon name="arrow" size={16} /></button></section><button className="graph-shortcut" onClick={() => onNavigate('graph')}><span className="metric-icon"><Icon name="graph" /></span><span><strong>Knowledge Graph</strong><small>업무규칙부터 실행까지, 관계를 추적하세요</small></span><Icon name="arrow" size={18} /></button></div></div>
    </div>
    <div hidden={view !== 'requirements'} className="requirement-layout">
      <section className="card requirement-form-card"><div className="card-heading"><div><p className="eyebrow">NEW REQUIREMENT</p><h2>새 요구사항 등록</h2></div><Icon name="requirements" /></div><form onSubmit={create} aria-label="요구사항 등록"><label htmlFor="requirement-title-input">제목 <span>최대 200자</span></label><input id="requirement-title-input" value={title} onChange={e => setTitle(e.target.value)} required maxLength={200} disabled={busy} placeholder="예: 대여 승인 권한 검증" /><div className="label-row"><label htmlFor="requirement-description">상세 내용</label><span>{description.length.toLocaleString()} / 10,000</span></div><textarea id="requirement-description" value={description} onChange={e => setDescription(e.target.value)} required maxLength={10000} rows={9} disabled={busy} placeholder="업무의 목적과 조건, 예외 상황을 구체적으로 작성해 주세요." /><p className="field-hint">명확한 업무조건은 분석과 테스트의 출발점이 됩니다.</p><div className="form-footer"><span>등록 후 AI 분석을 시작할 수 있습니다.</span><button type="submit" disabled={busy}>{busy ? <><span className="spinner" /> 저장 중…</> : '요구사항 저장'}</button></div></form></section>
      <section className="card requirement-summary"><p className="eyebrow">REQUIREMENT DETAILS</p>{result ? <article className="requirement-result" aria-label="요구사항 상세"><span className={`status-badge status-${result.status}`}>{result.status}</span><h3>{result.title}</h3><p className="requirement-description">{result.description}</p><dl><dt>등록 일시</dt><dd>{new Date(result.createdAt).toLocaleString('ko-KR')}</dd><dt>Requirement ID</dt><dd><code>{result.id}</code></dd></dl><button onClick={() => onNavigate('analysis')}>AI 분석으로 이동 <Icon name="arrow" size={17} /></button></article> : <div className="empty-state"><Icon name="requirements" size={34} /><h3>요구사항을 기다리고 있습니다</h3><p>새 요구사항을 등록하거나<br />상단 ID 조회로 상세 내용을 확인하세요.</p></div>}</section>
    </div>
    {needsRequirement && <section className="card empty-state"><span className="empty-icon"><Icon name="requirements" size={28} /></span><h2>먼저 요구사항을 선택해 주세요</h2><p>상단에서 Requirement ID를 조회하거나 요구사항 관리에서 새 요구사항을 등록하세요.</p><button onClick={() => onNavigate('requirements')}>요구사항 관리로 이동 <Icon name="arrow" size={16} /></button><button className="text-button" onClick={() => onNavigate('evaluation')}>Frozen 평가 샘플 찾아보기</button></section>}
    <div hidden={view !== 'analysis'}>{result && <RequirementAnalysis key={`analysis:${result.id}`} requirementId={result.id} onBusyChange={onAnalysisBusy} onSummary={setAnalysisSummary} onSaved={() => setResult(current => current && current.status === 'DRAFT' ? { ...current, status: 'ANALYZED' } : current)} />}</div>
    <div hidden={!['testcases', 'review', 'execution'].includes(view)}>{result && <TestCases key={`tests:${result.id}`} requirementId={result.id} view={view} onNavigate={onNavigate} onSummary={setTestSummary} />}</div>
    <div hidden={view !== 'evaluation'}><Evaluations key={`evaluation:${result?.id ?? 'none'}`} requirementId={result?.id ?? ''} requirementBusy={busy} onSelectRequirement={loadRequirement} /></div>
    <div hidden={view !== 'graph'}>{result && <KnowledgeGraph key={`graph:${result.id}`} requirementId={result.id} />}</div>
    {toast && <div className="toast" role="status"><span className="toast-icon"><Icon name="check" /></span><div><strong>등록 완료</strong><span>{toast}</span></div><button className="icon-button" aria-label="알림 닫기" onClick={() => setToast('')}><Icon name="close" size={17} /></button></div>}
  </div>
}
