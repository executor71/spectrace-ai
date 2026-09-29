import { useEffect, useState } from 'react'
import Requirements from './Requirements'

type ServiceState = 'checking' | 'online' | 'offline'

type ServiceStatus = {
  name: string
  detail: string
  state: ServiceState
}

const initialServices: ServiceStatus[] = [
  { name: 'Spring Boot', detail: '업무 API · :8080', state: 'checking' },
  { name: 'AI Service', detail: 'RAG 연결 · :8000', state: 'checking' },
]

async function checkService(url: string): Promise<boolean> {
  try {
    const response = await fetch(url)
    if (!response.ok) return false
    const body = await response.json()
    return body.status === 'UP'
  } catch {
    return false
  }
}

export default function App() {
  const [services, setServices] = useState(initialServices)

  useEffect(() => {
    let active = true
    Promise.all([
      checkService('/actuator/health'),
      checkService('/ai-health/health'),
    ]).then(([backendOnline, aiOnline]) => {
      if (!active) return
      setServices([
        { ...initialServices[0], state: backendOnline ? 'online' : 'offline' },
        { ...initialServices[1], state: aiOnline ? 'online' : 'offline' },
      ])
    })
    return () => {
      active = false
    }
  }, [])

  return (
    <main className="shell">
      <header className="topbar">
        <a className="wordmark" href="#home" aria-label="Legacy Change Assistant 홈">
          <span className="mark">LC</span>
          <span>LEGACY CHANGE ASSISTANT</span>
        </a>
        <span className="environment"><span className="environment-dot" /> LOCAL POC</span>
      </header>

      <section className="intro" id="home">
        <p className="eyebrow">ENGINEERING WORKBENCH <span> / </span> 01</p>
        <h1>변경 요청을<br /><em>근거와 함께.</em></h1>
        <p className="lede">업무 규칙과 API 명세를 찾아 요구사항을 분석하고, 검토할 테스트 초안을 준비합니다.</p>
      </section>

      <Requirements />

      <section className="workspace" aria-labelledby="workspace-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">WORKSPACE STATUS</p>
            <h2 id="workspace-title">서비스 연결</h2>
          </div>
          <span className="read-only">SKELETON</span>
        </div>
        <div className="service-list">
          {services.map((service, index) => (
            <article className="service-row" key={service.name}>
              <span className="service-index">0{index + 1}</span>
              <div className="service-name">
                <h3>{service.name}</h3>
                <p>{service.detail}</p>
              </div>
              <span className={`status status-${service.state}`}>
                <span className="status-dot" />
                {service.state === 'checking' ? '확인 중' : service.state === 'online' ? '정상' : '연결 안 됨'}
              </span>
            </article>
          ))}
          <article className="service-row database-row">
            <span className="service-index">03</span>
            <div className="service-name">
              <h3>PostgreSQL + pgvector</h3>
              <p>app · rag · evaluation schemas</p>
            </div>
            <span className="status status-managed"><span className="status-dot" /> AI health로 확인</span>
          </article>
        </div>
      </section>

      <footer className="footer">
        <span>LEGACY SYSTEMS / CHANGE ANALYSIS</span>
        <span>01 — FOUNDATION</span>
      </footer>
    </main>
  )
}
