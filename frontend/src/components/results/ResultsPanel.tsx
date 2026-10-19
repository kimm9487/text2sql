import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { COUNTRY_LABEL, formatValue } from '../../lib/format'
import type { ChatMessage, QueryResponse } from '../../types'
import ChartView from './ChartView'
import ResultTable from './ResultTable'
import StepTrace from './StepTrace'

type Tab = 'result' | 'chart' | 'sql' | 'steps'

const SQL_KEYWORDS = /\b(SELECT|FROM|WHERE|AND|OR|GROUP BY|ORDER BY|LIMIT|JOIN|LEFT JOIN|ON|AS|SUM|COUNT|DISTINCT|COALESCE|ROUND|OVER|WITH|DESC|ASC|IS NOT NULL|NULL|CASE|WHEN|THEN|ELSE|END|IN|HAVING|UNION)\b/g

// 키워드·문자열만 색을 입히는 간단한 하이라이터 (HTML 삽입 없이 React 노드로)
function highlightSql(sql: string): ReactNode[] {
  const out: ReactNode[] = []
  const parts = sql.split(/('(?:[^']|'')*')/g)
  parts.forEach((part, i) => {
    if (part.startsWith("'")) {
      out.push(<span key={`s${i}`} className="str">{part}</span>)
      return
    }
    let last = 0
    for (const m of part.matchAll(SQL_KEYWORDS)) {
      const idx = m.index ?? 0
      if (idx > last) out.push(part.slice(last, idx))
      out.push(<span key={`k${i}-${idx}`} className="kw">{m[0]}</span>)
      last = idx + m[0].length
    }
    if (last < part.length) out.push(part.slice(last))
  })
  return out
}

function defaultTab(r: QueryResponse): Tab {
  if (r.status === 'success' && r.rows.length) return 'result'
  return 'steps'
}

export default function ResultsPanel({ message }: { message: ChatMessage | null }) {
  const r = message?.response
  const [tab, setTab] = useState<Tab>('result')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (r) setTab(defaultTab(r))
  }, [message?.id, r])

  if (!message) {
    return (
      <div className="results-panel">
        <div className="results-empty">
          <span className="brand-mark" style={{ width: 44, height: 44, borderRadius: 12 }}>SQL</span>
          <div>왼쪽에서 질문하면<br />SQL·결과 표·차트·처리 단계가 여기에 표시됩니다</div>
        </div>
      </div>
    )
  }

  if (message.loading || !r) {
    return (
      <div className="results-panel">
        <div className="results-empty">
          {message.loading ? <><span className="spinner" /> <div>SQL 생성·조회 중…</div></> : <div>{message.error}</div>}
        </div>
      </div>
    )
  }

  const copySql = () => {
    if (!r.sql) return
    navigator.clipboard?.writeText(r.sql).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => undefined)
  }

  const tabs: { key: Tab; label: string; show: boolean }[] = [
    { key: 'result', label: '결과', show: r.status === 'success' },
    { key: 'chart', label: '차트', show: !!r.chart },
    { key: 'sql', label: 'SQL', show: !!r.sql },
    { key: 'steps', label: '처리 단계', show: true },
  ]

  return (
    <div className="results-panel">
      <div className="results-head">
        <p className="results-question">{r.question}</p>
        <div className="results-meta">
          <span className="badge">{COUNTRY_LABEL[r.country] ?? r.country}</span>
          {r.date_range && <span className="badge">{r.date_range.label} ({r.date_range.start} ~ {r.date_range.end})</span>}
          {r.sql_source === 'template' && <span className="badge">템플릿 · {r.template?.title}</span>}
          {r.sql_source === 'llm' && <span className="badge badge-accent">LLM · {r.llm?.model}</span>}
          {r.status === 'success' && <span className="badge badge-success">{r.row_count.toLocaleString()}행</span>}
          {r.masked_count > 0 && <span className="badge badge-warning">개인정보 {r.masked_count}건 마스킹</span>}
          <span className="badge">{r.elapsed_ms.toLocaleString()}ms</span>
          <span className="results-actions">
            <button className="btn btn-sm" disabled title="기말 구현 예정">CSV 다운로드</button>
            <button className="btn btn-sm" disabled title="기말 구현 예정">리포트 공유</button>
          </span>
        </div>
        <div className="tabs" role="tablist">
          {tabs.filter(t => t.show).map(t => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} className={`tab ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="results-body">
        {r.status === 'blocked' && <div className="alert alert-danger"><b>차단됨</b> — {r.message}</div>}
        {r.status === 'error' && <div className="alert alert-warning"><b>처리 실패</b> — {r.message}</div>}
        {r.status === 'chat' && <div className="alert alert-info">{r.message}</div>}

        {tab === 'result' && r.status === 'success' && (
          <>
            {r.rows.length === 0 && <div className="alert alert-info">{r.message ?? '조건에 맞는 데이터가 없습니다.'}</div>}
            {r.summary.length > 0 && (
              <div className="summary-grid">
                {r.summary.map(c => (
                  <div key={c.label} className="card summary-card">
                    <div className="label" title={c.label}>{c.label}</div>
                    <div className="value">{formatValue(c.value)}{c.unit && <span style={{ fontSize: 13, marginLeft: 2 }}>{c.unit}</span>}</div>
                  </div>
                ))}
              </div>
            )}
            {r.rows.length > 0 && <ResultTable columns={r.columns} rows={r.rows} />}
            {r.warnings.length > 0 && <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>참고: {r.warnings.join(' / ')}</p>}
            <div className="placeholder-box" style={{ marginTop: 16 }}>
              <span className="badge badge-todo">기말 구현 예정</span>{' '}
              AI 인사이트 — 숫자는 코드가 계산하고, LLM 은 결과 해석 문장과 후속 질문 추천만 작성하도록 붙일 예정
            </div>
          </>
        )}

        {tab === 'chart' && r.chart && <ChartView spec={r.chart} rows={r.rows} />}

        {tab === 'sql' && r.sql && (
          <>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
              <button className="btn btn-sm" onClick={copySql}>{copied ? '복사됨' : 'SQL 복사'}</button>
            </div>
            <pre className="sql-box">{highlightSql(r.sql)}</pre>
            <dl className="kv">
              <dt>생성 방식</dt>
              <dd>{r.sql_source === 'template' ? `결정적 템플릿 (${r.template?.name})` : `LLM 생성 (${r.llm?.model}, ${r.llm?.latency_ms.toLocaleString()}ms)`}</dd>
              {r.template?.notes.map(n => (
                <Fragment key={n}><dt>지표 기준</dt><dd>{n}</dd></Fragment>
              ))}
              <dt>실행 방식</dt>
              <dd>읽기전용 커넥션, 시간 제한 5초, 최대 1,000행</dd>
            </dl>
          </>
        )}

        {tab === 'steps' && <StepTrace steps={r.steps} chat={r.status === 'chat'} />}
      </div>
    </div>
  )
}
