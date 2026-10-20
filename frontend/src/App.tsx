import { useEffect, useRef, useState } from 'react'
import Requirements from './Requirements'
import Icon from './Icon'
import { screens } from './navigation'
import type { Screen } from './navigation'

type ServiceState = 'checking' | 'online' | 'offline'
const initialScreen = () => screens.find(item => item.id === window.location.hash.slice(1))?.id ?? 'dashboard'
export default function App() {
  const [view, setView] = useState<Screen>(initialScreen)
  const [drawer, setDrawer] = useState(false)
  const [analysisBusy, setAnalysisBusy] = useState(false)
  const [services, setServices] = useState<ServiceState[]>(['checking', 'checking'])
  const menu = useRef<HTMLButtonElement>(null)
  const sidebar = useRef<HTMLElement>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const current = screens.find(item => item.id === view)!
  useEffect(() => {
    const change = () => { const next = screens.find(item => item.id === window.location.hash.slice(1)); if (next) setView(next.id) }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  useEffect(() => {
    document.title = `${current.label} | SpecTrace AI`
    heading.current?.focus({ preventScroll: true })
  }, [current.label])
  useEffect(() => {
    if (drawer) sidebar.current?.querySelector<HTMLButtonElement>('button')?.focus()
  }, [drawer])
  useEffect(() => {
    const controller = new AbortController()
    async function check() {
      const values = await Promise.all(['/actuator/health', '/ai-health/health'].map(async url => {
        try {
          const response = await fetch(url, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]) })
          return response.ok && (await response.json()).status === 'UP' ? 'online' : 'offline'
        } catch { return 'offline' }
      }))
      if (!controller.signal.aborted) setServices(values as ServiceState[])
    }
    void check(); const timer = setInterval(check, 30000)
    return () => { clearInterval(timer); controller.abort() }
  }, [])
  function closeDrawer() { setDrawer(false); menu.current?.focus() }
  function navigate(id: Screen) {
    setView(id); window.history.pushState(null, '', `#${id}`)
    if (drawer) closeDrawer()
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">본문으로 이동</a>
    {drawer && <button className="drawer-backdrop" aria-label="메뉴 닫기" onClick={closeDrawer} />}
    <aside id="app-sidebar" ref={sidebar} className={`sidebar ${drawer ? 'is-open' : ''}`} aria-label="워크스페이스 메뉴" role={drawer ? 'dialog' : undefined} aria-modal={drawer || undefined} onKeyDown={e => {
      if (!drawer) return
      if (e.key === 'Escape') { e.preventDefault(); closeDrawer() }
      if (e.key === 'Tab') {
        const buttons = sidebar.current?.querySelectorAll<HTMLButtonElement>('button')
        if (!buttons?.length) return
        if (e.shiftKey && document.activeElement === buttons[0]) { e.preventDefault(); buttons[buttons.length - 1].focus() }
        else if (!e.shiftKey && document.activeElement === buttons[buttons.length - 1]) { e.preventDefault(); buttons[0].focus() }
      }
    }}>
      <div className="brand"><span className="brand-mark"><Icon name="graph" size={25} /></span><span>SpecTrace <small>AI</small></span><button className="icon-button drawer-close" onClick={closeDrawer} aria-label="메뉴 닫기"><Icon name="close" /></button></div>
      <div className="workspace-label"><span className="workspace-avatar">S</span><div>Engineering workspace<small>변경 요청부터 테스트 검증까지</small></div></div>
      <p className="nav-label">WORKSPACE</p>
      <nav aria-label="주 메뉴">{screens.filter(item => item.id !== 'evaluation').map((item, i) => <button key={item.id} onClick={() => navigate(item.id)} aria-current={view === item.id ? 'page' : undefined}><Icon name={item.id} /><span>{item.label}</span><small>{String(i + 1).padStart(2, '0')}</small></button>)}</nav>
      <p className="nav-label technical-nav-label">기술 검증·관리</p><nav aria-label="기술 메뉴"><button onClick={() => navigate('evaluation')} aria-current={view === 'evaluation' ? 'page' : undefined}><Icon name="evaluation" /><span>기술 검증·관리</span></button></nav>
      <div className="sidebar-footer"><span className="live-dot" /><div>근거에서 검증까지<small>개발자의 검토와 승인으로 완성합니다</small></div></div>
    </aside>
    <div className="app-body">
      <header className="app-header">
        <div className="breadcrumb"><button ref={menu} className="icon-button mobile-menu" onClick={() => setDrawer(true)} aria-expanded={drawer} aria-controls="app-sidebar" aria-label="메뉴 열기"><Icon name="menu" /></button><span>SpecTrace AI</span><span className="breadcrumb-separator">/</span><strong>{current.path}</strong></div>
        <div className="header-status">{['업무 서비스', '분석 서비스'].map((name, i) => <span key={name} className={`connection connection-${services[i]}`}><span />{name}<span className="sr-only">{services[i] === 'online' ? ' 정상' : services[i] === 'offline' ? ' 연결 안 됨' : ' 확인 중'}</span></span>)}<span className={`analysis-indicator ${analysisBusy ? 'is-running' : ''}`} role="status">{analysisBusy ? <><span className="spinner" /> 분석 처리 중</> : <><span className="live-dot" /> 분석 대기</>}</span></div>
      </header>
      <main id="main-content" className="main-content" tabIndex={-1}>
        <div className="page-heading"><div><p className="eyebrow">WORKSPACE / {current.path.toUpperCase()}</p><h1 tabIndex={-1} ref={heading}>{current.label}</h1><p className={view === 'dashboard' ? 'service-purpose' : undefined}>{current.description}</p></div><span className="environment-pill">LOCAL WORKSPACE</span></div>
        <Requirements view={view} onNavigate={navigate} onAnalysisBusy={setAnalysisBusy} />
        <footer className="page-footer"><span>SpecTrace AI <span>·</span> 변경 요청을 근거와 테스트로 검증</span><span>합성 업무 예제로 체험하는 로컬 환경</span></footer>
      </main>
    </div>
  </div>
}
