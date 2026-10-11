import { useState } from 'react'
import './KnowledgeGraph.css'

type Node = { type: string; id: string; title?: string; scenario?: string; method?: string; pathTemplate?: string; section?: string; result?: string; testCaseId?: string; testCaseRevision?: number; reviewRevision?: number; executedAt?: string; approvalStatus?: string }
type Path = { path: Node[]; relations: string[]; evidenceChunkIds: string[] }
type Graph = { root: Node; relatedBusinessRules: Node[]; relatedApis: Node[]; relatedTestCases: Node[]; evidence: Node[]; executions: Node[]; paths: Path[]; nodeCount: number; edgeCount: number }

export default function KnowledgeGraph({ requirementId }: { requirementId: string }) {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [detail, setDetail] = useState<Graph | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function load(tool: string, body: Record<string, string>, overview = false) {
    setBusy(true); setError('')
    try {
      const r = await fetch(`/api/graph/${tool}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(10000) })
      if (!r.ok) throw new Error(r.status === 404 ? '동기화된 관계가 없습니다.' : 'Graph 기능을 사용할 수 없습니다. 기존 분석과 테스트 기능은 계속 사용할 수 있습니다.')
      const value: Graph = await r.json()
      if (overview) { setGraph(value); setDetail(null) } else setDetail(value)
    } catch (e) { setError(e instanceof Error ? e.message : 'Graph 조회 실패') }
    finally { setBusy(false) }
  }
  const title = (n: Node) => n.title || n.scenario || n.section || (n.method ? `${n.method} ${n.pathTemplate}` : n.result || n.type)
  const latest = (g: Graph, t: Node) => g.executions.filter(e => e.testCaseId === t.id).sort((a,b) => (b.executedAt || '').localeCompare(a.executedAt || ''))[0]
  function card(n: Node) {
    const g = detail || graph
    const ex = g && n.type === 'TestCase' ? latest(g,n) || (graph ? latest(graph,n) : undefined) : undefined
    return <div className={`kg-node kg-${n.type}`}>
      <span className="kg-kind">{n.type}</span><strong>{title(n)}</strong><code>{n.id}</code>
      {n.approvalStatus && <span>{n.approvalStatus} · revision {n.reviewRevision}</span>}
      {ex && <span className={`kg-result kg-${ex.result}`}>{ex.result} · 실행 당시 revision {ex.testCaseRevision}</span>}
      {n.type === 'BusinessRule' && <button disabled={busy} onClick={() => load('find_impacted_tests', { businessRuleId: n.id })}>영향 경로</button>}
      {n.type === 'TestCase' && <button disabled={busy} onClick={() => load('trace_test_case_origin', { testCaseId: n.id })}>생성 근거 추적</button>}
    </div>
  }
  return <section className="knowledge-graph" aria-label="Knowledge Graph">
    <div className="section-heading"><div><p className="eyebrow">RELATIONSHIP EXPLORER</p><h3>요구사항 관계 추적</h3></div><button disabled={busy} onClick={() => load('find_requirement_context', { requirementId }, true)}>{busy ? '관계 조회 중…' : '관계 그래프 조회'}</button></div>
    <p>명시적 동기화 시점의 관계입니다. 실행 결과는 실행 당시 revision과 함께 표시합니다.</p>
    {error && <p role="alert" className="form-error">{error}</p>}
    {graph && <div className="kg-overview">
      <p>{graph.nodeCount} nodes · {graph.edgeCount} relations · 근거가 확인된 관계만 표시</p>
      {card(graph.root)}
      <div className="kg-columns">{['BusinessRule','Api','TestCase'].map(kind => <div key={kind}><h4>↓ {kind}</h4>{(kind === 'BusinessRule' ? graph.relatedBusinessRules : kind === 'Api' ? graph.relatedApis : graph.relatedTestCases).map(n => <div key={n.id}>{card(n)}</div>)}</div>)}</div>
      <details><summary>Requirement → Rule → API → TestCase 경로</summary>{graph.paths.filter(p => p.relations.length === 3).map((p,i) => <div className="kg-path" key={i}>{p.path.map((n,j) => <span key={j}><b>{n.type}</b><code>{n.id}</code>{j < p.relations.length && <small>↓ {p.relations[j]}</small>}</span>)}</div>)}</details>
    </div>}
    {detail && <div className="kg-detail" aria-label="선택한 관계 경로"><h4>{detail.root.type === 'BusinessRule' ? '업무규칙 영향 경로' : '테스트 생성 근거 및 실행 이력'}</h4>{card(detail.root)}
      {detail.paths.filter(p => p.relations.length >= 2 && !p.relations.includes('EXECUTED_AS')).map((p,i) => <div className="kg-path" key={i}>{p.path.map((n,j) => <span key={j}><b>{n.type}</b><code>{n.id}</code>{j < p.relations.length && <small>↓ {p.relations[j]}</small>}</span>)}</div>)}
      <div className="kg-history">{detail.executions.slice().sort((a,b) => (b.executedAt || '').localeCompare(a.executedAt || '')).slice(0,5).map(e => <div key={e.id}><b className={`kg-result kg-${e.result}`}>{e.result}</b> · revision {e.testCaseRevision}<code>{e.id}</code><span>{e.executedAt}</span></div>)}</div>
      <details><summary>관련 Evidence ({detail.evidence.length})</summary>{detail.evidence.map(n => <div key={n.id}>{card(n)}</div>)}</details>
    </div>}
  </section>
}
