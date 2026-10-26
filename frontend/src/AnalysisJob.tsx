import { useEffect, useRef, useState } from 'react'
import './analysis-jobs.css'
export type Job = {jobId:string;requirementId:string;status:string;stage:string;createdAt:string;startedAt:string|null;completedAt:string|null;elapsedSeconds:number;queuePosition:number|null;errorCode:string|null;errorMessage:string|null;message:string;resultAvailable:boolean}
const active = (job:Job|null) => !!job && ['QUEUED','RUNNING'].includes(job.status)
const labels:Record<string,string>={QUEUED:'대기 중',RUNNING:'AI 분석 진행 중',SUCCEEDED:'분석 완료',FAILED:'분석 실패',TIMED_OUT:'분석 시간 초과',CANCELLED:'대기 작업 취소'}
const stages:Record<string,string>={WAITING:'실행 순서 대기',LLM_ANALYSIS:'AI 서비스에서 분석 처리 중',VALIDATING_OUTPUT:'결과 형식·근거 검증',SAVING_RESULT:'분석 결과 저장',COMPLETED:'저장 완료'}
async function read(url:string,options?:RequestInit){const response=await fetch(url,{...options,signal:AbortSignal.timeout(15000)});const body=await response.json().catch(()=>null);if(!response.ok)throw new Error(body?.message||`조회 실패 (HTTP ${response.status})`);return body}
export default function AnalysisJob({requirementId,onComplete,onBusyChange,onShowResult}:{requirementId:string;onComplete:()=>void;onBusyChange:(busy:boolean)=>void;onShowResult:()=>void}){
 const [job,setJob]=useState<Job|null>(null),[pending,setPending]=useState(false),[connectionError,setConnectionError]=useState(''),[seconds,setSeconds]=useState(0)
 const seen=useRef(new Set<string>()),callbacks=useRef({onComplete,onBusyChange});callbacks.current={onComplete,onBusyChange}
 function accept(value:Job|null){setJob(value);setConnectionError('');if(value?.status==='SUCCEEDED'&&!seen.current.has(value.jobId)){seen.current.add(value.jobId);callbacks.current.onComplete()}}
 async function refresh(){try{const jobs:Job[]=await read(`/api/requirements/${encodeURIComponent(requirementId)}/analysis-jobs`);accept(jobs[0]??null)}catch(e){setConnectionError(e instanceof Error?e.message:'연결 상태를 확인할 수 없습니다.')}}
 useEffect(()=>{let alive=true;setJob(null);setConnectionError('');read(`/api/requirements/${encodeURIComponent(requirementId)}/analysis-jobs`).then(jobs=>{if(alive)accept(jobs[0]??null)}).catch(e=>{if(alive)setConnectionError(e.message)});return()=>{alive=false}},[requirementId])
 useEffect(()=>{callbacks.current.onBusyChange(active(job));return()=>callbacks.current.onBusyChange(false)},[job?.status,job?.jobId])
 useEffect(()=>{
  if(!active(job))return
  let alive=true;let timer:ReturnType<typeof setTimeout>
  async function poll(){try{const value:Job=await read(`/api/analysis-jobs/${job!.jobId}`);if(alive)accept(value)}catch(e){if(alive)setConnectionError(e instanceof Error?e.message:'연결 문제')}finally{if(alive)timer=setTimeout(poll,document.hidden?15000:2500)}}
  const visibility=()=>{clearTimeout(timer);timer=setTimeout(poll,document.hidden?15000:0)}
  timer=setTimeout(poll,document.hidden?15000:2500);document.addEventListener('visibilitychange',visibility)
  return()=>{alive=false;clearTimeout(timer);document.removeEventListener('visibilitychange',visibility)}
 },[job?.jobId,job?.status])
 useEffect(()=>{if(!job){setSeconds(0);return}const update=()=>setSeconds(job.completedAt?job.elapsedSeconds:Math.max(job.elapsedSeconds,Math.floor((Date.now()-Date.parse(job.createdAt))/1000)));update();if(!active(job))return;const timer=setInterval(update,1000);return()=>clearInterval(timer)},[job])
 async function start(){if(pending||active(job))return;setPending(true);try{accept(await read(`/api/requirements/${encodeURIComponent(requirementId)}/analysis-jobs`,{method:'POST'}))}catch(e){setConnectionError(`${e instanceof Error?e.message:'접수 오류'} 접수되었을 수 있으니 진행 상태 새로고침으로 확인하세요.`)}finally{setPending(false)}}
 async function cancel(){if(!job||job.status!=='QUEUED'||pending)return;setPending(true);try{accept(await read(`/api/analysis-jobs/${job.jobId}/cancel`,{method:'POST'}))}catch(e){setConnectionError(e instanceof Error?e.message:'취소 실패')}finally{setPending(false)}}
 return <section className="analysis-job" aria-label="AI 분석 Job 상태">
  <div className="job-actions"><button onClick={()=>void start()} disabled={pending||active(job)}>{pending?'접수 중…':'변경 요청 분석 시작'}</button><button className="secondary" disabled={pending} onClick={()=>void refresh()}>진행 상태 새로고침</button></div>
  {connectionError&&<p className="form-error" role="alert">진행 상태 연결 문제: {connectionError} Job의 실제 실패와는 별개입니다. 자동으로 새 분석을 시작하지 않습니다.</p>}
  {job&&<div className={`job-state job-${job.status}`} role="status"><div className="job-status-line"><strong>{active(job)&&<span className="spinner"/>}{labels[job.status]??job.status}</strong><span>경과시간 {Math.floor(seconds/60).toString().padStart(2,'0')}:{(seconds%60).toString().padStart(2,'0')}</span></div><p>현재 단계: {stages[job.stage]??job.stage}{job.status==='QUEUED'&&job.queuePosition!==null&&` · 대기 순서 ${job.queuePosition}번`}</p><p>{job.message}</p><small>Job ID: <code>{job.jobId}</code></small>{job.errorCode&&<p>오류: {job.errorCode} · {job.errorMessage}</p>}<div className="job-actions">{job.status==='QUEUED'&&<button className="secondary" disabled={pending} onClick={()=>void cancel()}>대기 작업 취소</button>}{['SUCCEEDED','FAILED','TIMED_OUT'].includes(job.status)&&<button className="secondary" onClick={onShowResult}>저장된 분석 결과 확인</button>}{['FAILED','TIMED_OUT'].includes(job.status)&&<button disabled={pending} onClick={()=>void start()}>재시도</button>}</div>{active(job)&&<p>화면을 이동하거나 새로고침해도 접수된 작업은 계속됩니다. 상세 검색·추론 단계의 진행률은 제공되지 않습니다.</p>}</div>}
 </section>
}
export function AnalysisJobOverview({requirementId,refreshKey,onSelect,enabled}:{requirementId:string;refreshKey?:string;onSelect:(id:string)=>void;enabled:boolean}){
 const [data,setData]=useState<{running:number;queued:number;succeeded:number;failed:number;jobs:Job[]}|null>(null),[error,setError]=useState('')
 useEffect(()=>{if(!enabled)return;let alive=true;let timer:ReturnType<typeof setTimeout>;async function load(){try{const value=await read('/api/analysis-jobs'+(requirementId?`?requirementId=${encodeURIComponent(requirementId)}`:''));if(alive){setData(value);setError('')}}catch(e){if(alive)setError(e instanceof Error?e.message:'Job 현황 조회 실패')}finally{if(alive)timer=setTimeout(load,document.hidden?15000:5000)}}void load();return()=>{alive=false;clearTimeout(timer)}},[requirementId,refreshKey,enabled])
 return <section className="card job-overview" aria-label="분석 Job 현황"><h3>AI 분석 작업 현황</h3><p>현재 진행·대기 건수와 최근 24시간 완료 건수입니다. 분석 결과 수나 테스트 FAIL과 다른 지표입니다.</p>{error?<p role="alert">연결 문제: {error}</p>:!data?<p role="status">작업 현황 조회 중…</p>:<><div className="job-counts">{[['진행 중인 AI 분석',data.running],['대기 중인 AI 분석',data.queued],['최근 성공 분석',data.succeeded],['최근 실패·시간 초과 분석',data.failed]].map(([name,n])=><div key={name}><span>{name}</span><strong>{n}<small>건</small></strong></div>)}</div>{!data.jobs.length?<p>접수된 분석 Job이 없습니다. 기존 저장 분석 결과는 그대로 이용할 수 있습니다.</p>:<ul className="job-list">{data.jobs.slice(0,6).map(j=><li key={j.jobId}><button className="text-button" onClick={()=>onSelect(j.requirementId)}>{labels[j.status]} · {new Date(j.createdAt).toLocaleString('ko-KR')} · 변경 요청 보기</button></li>)}</ul>}</>}</section>
}
