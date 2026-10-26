import { AnalysisJobOverview } from './AnalysisJob'
import { TechnicalGuide } from './GettingStarted'
import { useEffect, useState } from 'react'
import type { Screen } from './navigation'

type Counts = Record<string, number>
type Row = { id: string; title: string; createdAt: string; hasAnalysis: boolean; stale: boolean; counts: Counts }
type Case = { testCaseId: string; requirementId: string; title: string; scenario: string; approvalStatus: string; executionStatus: string; reviewRevision: number; syntheticExecution: boolean }
type Data = { queriedAt: string; requirements: Row[]; cases: Case[]; counts: Counts; basis: string }
const names: Record<string,string> = { DRAFT: '검토 대기', APPROVED: '승인', REJECTED: '반려', PASS: 'PASS', FAIL: 'FAIL', ERROR: 'ERROR', NOT_RUN: '미실행' }
export default function Dashboard({ onSelect, onNavigate, active = true }: { active?: boolean; onSelect: (id: string, view: Screen, tc?: string) => Promise<void>; onNavigate: (view: Screen) => void }) {
  const [data,setData]=useState<Data|null>(null), [busy,setBusy]=useState(false), [error,setError]=useState('')
  const [page,setPage]=useState(0)
  const [scope,setScope]=useState(''), [filter,setFilter]=useState('ATTENTION'), [search,setSearch]=useState(''), [tab,setTab]=useState('work')
  async function load() {
    setBusy(true);setError('')
    try {
      const r=await fetch('/api/dashboard/summary',{signal:AbortSignal.timeout(30000)});const b=await r.json().catch(()=>null)
      if(!r.ok)throw new Error(b?.message||'업무 현황 조회 실패');setData(b)
    } catch(e){setError(e instanceof Error?e.message:'조회 실패')} finally{setBusy(false)}
  }
  useEffect(()=>{void load()},[])
  const rows=data?.requirements.filter(r=>!scope||r.id===scope)??[]
  useEffect(()=>setPage(0),[scope,search])
  const filteredRows=rows.filter(r=>r.title.toLowerCase().includes(search.toLowerCase()))
  const cases=data?.cases.filter(c=>!scope||c.requirementId===scope)??[]
  const counts: Counts={requirements:rows.length,total:cases.length,DRAFT:0,APPROVED:0,REJECTED:0,PASS:0,FAIL:0,ERROR:0,NOT_RUN:0,SYNTHETIC:0}
  cases.forEach(c=>{counts[c.approvalStatus]++;counts[c.executionStatus]++;if(c.syntheticExecution)counts.SYNTHETIC++})
  const denominator=counts.PASS+counts.FAIL
  const visible=cases.filter(c=>filter==='ALL'||filter==='ATTENTION'&&(c.approvalStatus==='DRAFT'||c.executionStatus==='FAIL')||c.approvalStatus===filter||c.executionStatus===filter)
  function focus(value:string){setFilter(value);requestAnimationFrame(()=>document.getElementById('dashboard-cases')?.scrollIntoView({behavior:'smooth',block:'start'}))}
  return <section className="phase13-dashboard" aria-busy={busy}>
    <div className="p13-heading"><div className="panel-title"><span className="eyebrow">SPECTRACE AI</span><h2>업무 현황</h2></div>
    <div className="workflow-tabs"><button className={tab==='work'?'active':''} onClick={()=>setTab('work')}>업무 현황</button><button className={tab==='tech'?'active':''} onClick={()=>setTab('tech')}>기술 검증 결과</button></div></div>
    {tab==='tech'?<TechnicalResults/>:<>
      <div className="card p13-toolbar"><label className="p13-scope"><span>요구사항 범위</span><select value={scope} onChange={e=>setScope(e.target.value)}><option value="">전체 요구사항</option>{data?.requirements.map(r=><option key={r.id} value={r.id}>{r.title}</option>)}</select></label><button className="secondary" disabled={busy} onClick={()=>void load()}>새로고침</button><button onClick={()=>onNavigate('requirements')}>새 변경 요청 입력</button><small>마지막 조회: {data?new Date(data.queriedAt).toLocaleString('ko-KR'):'—'}</small></div>
      <AnalysisJobOverview enabled={active && tab === 'work'} requirementId={scope} refreshKey={data?.queriedAt} onSelect={id => { void onSelect(id,'analysis') }} />
      {busy&&<p role="status">업무 현황 조회 중…</p>}{error&&<p className="form-error" role="alert">{error} <button disabled={busy} onClick={()=>void load()}>다시 조회</button></p>}
      {data&&!busy&&!error&&<>
        <div className="p13-summary"><div className="metric-grid">{[['등록 요구사항','requirements','REQUIREMENTS'],['현재 생성 TC','total','ALL'],['검토 대기 TC','DRAFT','DRAFT'],['최근 일반 실행 FAIL TC','FAIL','FAIL']].map(([label,key,target])=><button className="metric-card p13-metric" key={key} onClick={()=>target==='REQUIREMENTS'?document.getElementById('dashboard-requirements')?.scrollIntoView():focus(target)}><p>{label}</p><strong>{counts[key]}<small>건</small></strong><small>{key==='requirements'?'선택한 범위':'현재 batch · 현재 검토본 기준'}</small></button>)}</div>
        <p className="metadata p13-basis">{data.basis}</p></div>
        <div className="p13-chart-section"><div className="p13-charts">{[['검토 상태',['DRAFT','APPROVED','REJECTED']],['최신 일반 실행 결과',['PASS','FAIL','ERROR']]].map(([title,keys])=><section className="card" key={title as string}><h3>{title}</h3><div className="p13-bars" role="group" aria-label={title as string}>{(keys as string[]).map(key=><button key={key} className="p13-bar" onClick={()=>focus(key)} aria-label={`${names[key]} ${counts[key]}건`}><span>{names[key]} <b>{counts[key]}건</b></span><span className="p13-track"><span className={`p13-fill fill-${key}`} style={{width:`${cases.length?counts[key]/cases.length*100:0}%`}}/></span></button>)}</div><p>모수: 현재 생성 TC {cases.length}건</p></section>)}</div>
        <p className="p13-execution-note">일반 실행 PASS 비율: {denominator?`${(counts.PASS/denominator*100).toFixed(1)}% (${counts.PASS}/${denominator})`:'집계 대상 없음'} · ERROR {counts.ERROR}건 · 미실행 {counts.NOT_RUN}건 · 의도적 결함 실행 TC {counts.SYNTHETIC}건(일반 실행 통계 제외) · 차단: 미조회</p></div>
        <section className="card" id="dashboard-requirements"><div className="card-heading"><h3>최근 요구사항 목록</h3><label>제목 검색<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="요구사항 제목"/></label></div><div className="p13-table-wrap"><table className="p13-table"><thead><tr>{['요구사항 제목','생성 시각','저장 분석','TC','대기 / 승인 / 반려','현재 revision 실행','작업'].map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{filteredRows.slice(page*10,(page+1)*10).map(r=><tr key={r.id}><td><button className="text-button" onClick={()=>void onSelect(r.id,'requirements')}>{r.title}</button>{r.stale&&<small>분석 변경됨</small>}</td><td>{new Date(r.createdAt).toLocaleString('ko-KR')}</td><td>{r.hasAnalysis?'있음':'없음'}</td><td>{r.counts.total}건</td><td>{r.counts.DRAFT} / {r.counts.APPROVED} / {r.counts.REJECTED}</td><td>PASS {r.counts.PASS} · FAIL {r.counts.FAIL} · ERROR {r.counts.ERROR} · 미실행 {r.counts.NOT_RUN}</td><td><button className="secondary" onClick={()=>void onSelect(r.id,'requirements')}>상세 보기</button><ExportButton id={r.id}/></td></tr>)}</tbody></table></div><div className="p13-pagination"><span>전체 {filteredRows.length}건 · {page+1} / {Math.max(1,Math.ceil(filteredRows.length/10))} 페이지</span><button className="secondary" disabled={page===0} onClick={()=>setPage(p=>p-1)}>이전</button><button className="secondary" disabled={(page+1)*10>=filteredRows.length} onClick={()=>setPage(p=>p+1)}>다음</button></div>{!rows.filter(r=>r.title.toLowerCase().includes(search.toLowerCase())).length&&<p>표시할 요구사항이 없습니다.</p>}</section>
        <section className="card" id="dashboard-cases"><div className="card-heading"><h3>검토 대기 및 실행 항목</h3><label>목록 조건<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="ATTENTION">검토 대기 또는 FAIL</option><option value="ALL">전체 TC</option>{Object.entries(names).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label></div>{!visible.length?<p>해당 조건의 TC가 없습니다.</p>:<ul className="p13-case-list">{visible.map(c=><li key={c.testCaseId}><button className="text-button" onClick={()=>void onSelect(c.requirementId,c.executionStatus==='FAIL'?'execution':'review',c.testCaseId)}><strong>{c.scenario}</strong><span>{c.title} · {names[c.approvalStatus]} · {names[c.executionStatus]} · Revision {c.reviewRevision}</span></button></li>)}</ul>}</section>
      </>}
    </>}
  </section>
}

export function ExportButton({id}:{id:string}) {
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  async function download(){
    if(busy)return
    setBusy(true);setError('')
    try{
      const response=await fetch(`/api/requirements/${encodeURIComponent(id)}/reports/test-report.xlsx`,{signal:AbortSignal.timeout(60000)})
      if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(body?.message||body?.detail||`다운로드 실패 (HTTP ${response.status})`)}
      if(!response.headers.get('content-type')?.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))throw new Error('Excel 응답 형식이 올바르지 않습니다.')
      const blob=await response.blob();if(!blob.size)throw new Error('빈 보고서 응답입니다.')
      const disposition=response.headers.get('content-disposition')||''
      const encoded=disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
      const filename=encoded?decodeURIComponent(encoded):`SpecTrace_AI_${id}_검증보고서.xlsx`
      const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)
    }catch(e){setError(e instanceof Error?e.message:'Excel 다운로드 실패')}finally{setBusy(false)}
  }
  return <><button className="secondary" disabled={busy} onClick={()=>void download()}>{busy?'Excel 생성 중…':'Excel 다운로드'}</button>{error&&<span className="p13-download-error" role="alert">{error}</span>}</>
}

function TechnicalResults(){
  const [data,setData]=useState<any>(null),[error,setError]=useState('')
  useEffect(()=>{fetch('/technical-results.json').then(r=>{if(!r.ok)throw new Error('저장 실험 자료 조회 실패');return r.json()}).then(setData).catch(e=>setError(e.message))},[])
  return <section className="card"><h3>기술 검증 결과</h3><TechnicalGuide/><p>과거 소규모 합성 환경 실험이며 현재 업무 지표와 별개입니다. 업무시간 절감률: 미측정</p>{error?<p role="alert">{error}</p>:!data?<p role="status">저장 자료 조회 중…</p>:<><p>측정일: {data.measuredAt} · 평가 질의: {data.queryCount}개 · corpus: {data.corpusSize}개 chunk</p><p>모델: {data.models} · 평가셋: {data.datasetHash}</p><p>출처: {data.source} · 지연시간은 같은 실험의 warm 실행입니다.</p><div className="p13-table-wrap"><table className="p13-table"><thead><tr><th>검색 방식</th><th>Recall@5</th><th>MRR@5</th><th>nDCG@5</th><th>평균 지연(ms)</th><th>P95(ms)</th></tr></thead><tbody>{data.rows.map((r:any)=><tr key={r.strategy}><th>{r.strategy}</th><td>{r.recallAt5.toFixed(4)}</td><td>{r.mrrAt5.toFixed(4)}</td><td>{r.ndcgAt5.toFixed(4)}</td><td>{r.latencyMs.mean.toFixed(1)}</td><td>{r.latencyMs.p95.toFixed(1)}</td></tr>)}</tbody></table></div></>}</section>
}
