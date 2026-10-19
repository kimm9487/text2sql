import { useEffect, useRef } from 'react'
import { COUNTRY_LABEL, formatTime } from '../../lib/format'
import type { ChatMessage, QueryResponse } from '../../types'

interface Props {
  messages: ChatMessage[]
  selectedId: number | null
  examples: string[]
  onSelect: (id: number) => void
  onExample: (q: string) => void
}

function statusBadge(r: QueryResponse) {
  if (r.status === 'success') return <span className="badge badge-success">조회 완료</span>
  if (r.status === 'blocked') return <span className="badge badge-danger">차단</span>
  if (r.status === 'chat') return <span className="badge">안내</span>
  return <span className="badge badge-warning">실패</span>
}

function botText(m: ChatMessage): string {
  if (m.error) return m.error
  const r = m.response
  if (!r) return ''
  if (r.status === 'success') {
    const source = r.sql_source === 'template' ? `템플릿(${r.template?.title})` : 'LLM'
    const period = r.date_range ? ` · ${r.date_range.label}` : ''
    return `${source}로 SQL 을 만들어 ${r.row_count.toLocaleString()}행을 조회했습니다${period}. 오른쪽에서 결과를 확인하세요.`
  }
  return r.message ?? ''
}

export default function MessageList({ messages, selectedId, examples, onSelect, onExample }: Props) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  if (messages.length === 0) {
    return (
      <div className="empty-state">
        <span className="eyebrow">Text to SQL</span>
        <h2>데이터에 바로 질문하세요</h2>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          국가를 고르고 자연어로 물어보면 SQL 을 만들어 실행하고 표·차트로 보여줍니다.
          조회 대상은 과제용 가상 웹소설 플랫폼 DB 입니다.
        </p>
        <div className="example-list">
          {examples.map(q => (
            <button key={q} className="example-item" onClick={() => onExample(q)}>{q}</button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div>
      {messages.map(m => (
        <div key={m.id} className="msg">
          <div className="msg-user">
            <div>
              <div className="bubble">{m.question}</div>
              <div className="meta">{COUNTRY_LABEL[m.country]} · {formatTime(m.id)}</div>
            </div>
          </div>
          <div className={`msg-bot ${selectedId === m.id ? 'selected' : ''}`} onClick={() => onSelect(m.id)}>
            <div className="bot-avatar">SQL</div>
            <div className="bot-body">
              {m.loading ? (
                <div className="bot-title"><span className="spinner" /> <span className="muted">SQL 생성·조회 중…</span></div>
              ) : (
                <>
                  <div className="bot-title">
                    {m.response ? statusBadge(m.response) : <span className="badge badge-danger">오류</span>}
                    {m.response?.sql_source === 'llm' && <span className="badge badge-accent">LLM</span>}
                    {m.response?.sql_source === 'template' && <span className="badge">템플릿</span>}
                  </div>
                  <div className="bot-text">{botText(m)}</div>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  )
}
