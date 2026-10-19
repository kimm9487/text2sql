import { useEffect, useState } from 'react'
import Header from '../components/Header'
import GuideModal from '../components/GuideModal'
import CountrySelector from '../components/chat/CountrySelector'
import MessageInput from '../components/chat/MessageInput'
import MessageList from '../components/chat/MessageList'
import ResultsPanel from '../components/results/ResultsPanel'
import { getExamples, getHealth, runQuery } from '../lib/api'
import type { ChatMessage, Country, User } from '../types'

// 대화 기록은 지금은 브라우저에만 저장 (서버 저장·30일 자동 삭제는 기말 예정)
function storageKey(user: User) {
  return `t2s_messages_${user.login_id}`
}

function loadMessages(user: User): ChatMessage[] {
  try {
    const raw = localStorage.getItem(storageKey(user))
    const list = raw ? (JSON.parse(raw) as ChatMessage[]) : []
    return list.filter(m => !m.loading)
  } catch {
    return []
  }
}

export default function ChatPage({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadMessages(user))
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const list = loadMessages(user)
    return list.length ? list[list.length - 1].id : null
  })
  const [country, setCountry] = useState<Country>('ALL')
  const [examples, setExamples] = useState<string[]>([])
  const [llmEnabled, setLlmEnabled] = useState<boolean | null>(null)
  const [showGuide, setShowGuide] = useState(false)
  const loading = messages.some(m => m.loading)

  useEffect(() => {
    getExamples().then(r => setExamples(r.items)).catch(() => setExamples([]))
    getHealth().then(r => setLlmEnabled(r.llm.enabled)).catch(() => setLlmEnabled(null))
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(user), JSON.stringify(messages.slice(-30)))
    } catch {
      /* 저장 실패 무시 */
    }
  }, [messages, user])

  const ask = async (question: string) => {
    const id = Date.now()
    setMessages(prev => [...prev, { id, question, country, loading: true }])
    setSelectedId(id)
    try {
      const response = await runQuery(question, country)
      setMessages(prev => prev.map(m => (m.id === id ? { ...m, loading: false, response, country: response.country } : m)))
    } catch (err) {
      const error = err instanceof Error ? err.message : '요청에 실패했습니다'
      setMessages(prev => prev.map(m => (m.id === id ? { ...m, loading: false, error } : m)))
    }
  }

  const clearAll = () => {
    setMessages([])
    setSelectedId(null)
  }

  const selected = messages.find(m => m.id === selectedId) ?? null

  return (
    <div className="app-shell">
      <Header user={user} onLogout={onLogout}>
        {llmEnabled !== null && (
          <span className={`badge ${llmEnabled ? 'badge-success' : ''}`} title="템플릿에 없는 질문은 LLM 이 SQL 을 작성">
            LLM {llmEnabled ? '연결됨' : '미연결 (템플릿만)'}
          </span>
        )}
        <button className="btn btn-sm" onClick={() => setShowGuide(true)}>조회 가능한 데이터</button>
      </Header>

      <div className="chat-layout">
        <section className="chat-panel">
          <div className="message-scroll">
            <MessageList
              messages={messages}
              selectedId={selectedId}
              examples={examples}
              onSelect={setSelectedId}
              onExample={ask}
            />
          </div>
          <div className="composer">
            <div className="composer-top">
              <CountrySelector value={country} onChange={setCountry} />
              <div style={{ flex: 1 }} />
              {messages.length > 0 && <button className="btn btn-sm btn-ghost" onClick={clearAll} disabled={loading}>새 대화</button>}
            </div>
            <MessageInput disabled={loading} onSubmit={ask} />
          </div>
        </section>
        <ResultsPanel message={selected} />
      </div>

      {showGuide && <GuideModal onClose={() => setShowGuide(false)} />}
    </div>
  )
}
