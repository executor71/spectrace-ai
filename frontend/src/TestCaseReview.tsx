import { useState } from 'react'
import type { TestCase } from './TestCases'

export default function TestCaseReview({ current, stale, onSaved }: { current: TestCase; stale: boolean; onSaved: (value: TestCase) => void }) {
  const initial = { type: current.type, scenario: current.scenario, preconditions: current.preconditions.join('\n'), input: JSON.stringify(current.input, null, 2), steps: current.steps.join('\n'), expectedResult: JSON.stringify(current.expectedResult, null, 2) }
  const [form, setForm] = useState(initial)
  const [reviewer, setReviewer] = useState('demo/local')
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const dirty = JSON.stringify(form) !== JSON.stringify(initial)
  async function submit(action: 'save' | 'approve' | 'reject') {
    if (busy) return
    setBusy(true); setError('')
    try {
      const body = action === 'save' ? { reviewRevision: current.reviewRevision, type: form.type, scenario: form.scenario, preconditions: form.preconditions.trim() ? form.preconditions.split('\n') : [], input: JSON.parse(form.input), steps: form.steps.split('\n'), expectedResult: JSON.parse(form.expectedResult) } : { reviewRevision: current.reviewRevision, reviewer, reviewComment: comment }
      const response = await fetch(`/api/test-cases/${encodeURIComponent(current.testCaseId)}${action === 'save' ? '' : '/' + action}`, { method: action === 'save' ? 'PATCH' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(15000) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.message || '검토 저장에 실패했습니다.')
      onSaved(result)
    } catch (err) { setError(err instanceof SyntaxError ? 'Input과 Expected Result에 올바른 JSON을 입력해 주세요.' : err instanceof Error ? err.message : '검토 저장에 실패했습니다.') }
    finally { setBusy(false) }
  }
  return <section className="test-case-review" aria-label="테스트 검토">
    <h4>사용자 검토</h4>
    <p role="status">승인 상태: <strong>{current.approvalStatus}</strong> · {current.modified ? '사용자 수정본' : 'AI 원본'} · 실행 대상: {String(current.executionEligible)}</p>
    <p>검토자: {current.reviewer ?? '미검토'} · 검토 시각: {current.reviewedAt ? new Date(current.reviewedAt).toLocaleString('ko-KR') : '—'}</p>
    {current.reviewComment && <p>검토 의견: {current.reviewComment}</p>}
    <p>내용을 저장하면 DRAFT가 되어 다시 승인이 필요합니다. Evidence와 요구사항 연결은 변경할 수 없습니다.</p>
    <fieldset disabled={busy}>
      <legend>테스트 내용 수정</legend>
      <label htmlFor="review-type">Test Type</label>
      <select id="review-type" value={form.type} onChange={e => setForm({ ...form, type: e.target.value })}>{['NORMAL', 'EXCEPTION', 'AUTHORIZATION', 'BOUNDARY', 'BUSINESS_RULE'].map(type => <option key={type}>{type}</option>)}</select>
      {(['scenario', 'preconditions', 'input', 'steps', 'expectedResult'] as const).map(key => <div key={key}>
        <label htmlFor={'review-' + key}>{({ scenario: 'Scenario', preconditions: 'Preconditions (한 줄에 하나)', input: 'Input (JSON)', steps: 'Steps (한 줄에 하나)', expectedResult: 'Expected Result (JSON: description, assertions)' })[key]}</label>
        <textarea id={'review-' + key} rows={key === 'input' || key === 'expectedResult' ? 8 : 3} value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} />
      </div>)}
      <button type="button" disabled={!dirty} onClick={() => submit('save')}>수정 저장</button>
      {dirty && <p>저장하지 않은 수정이 있습니다. 저장 후 승인 또는 반려해 주세요.</p>}
      <label htmlFor="review-reviewer">검토자 (인증 없는 데모 사용자)</label><input id="review-reviewer" value={reviewer} maxLength={100} onChange={e => setReviewer(e.target.value)} />
      <label htmlFor="review-comment">검토 의견</label><textarea id="review-comment" value={comment} maxLength={4000} onChange={e => setComment(e.target.value)} />
      <div className="lookup-controls"><button type="button" disabled={dirty || stale} onClick={() => submit('approve')}>승인</button><button type="button" disabled={dirty} onClick={() => submit('reject')}>반려</button></div>
    </fieldset>
    {error && <p role="alert" className="form-error">{error}</p>}
    <details><summary>AI 생성 원본 보기 (읽기 전용)</summary><pre>{JSON.stringify(current.generatedContent, null, 2)}</pre></details>
  </section>
}
