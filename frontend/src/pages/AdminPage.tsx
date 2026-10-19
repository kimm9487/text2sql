import { useCallback, useEffect, useState } from 'react'
import Header from '../components/Header'
import { getLogs } from '../lib/api'
import { COUNTRY_LABEL } from '../lib/format'
import type { LogStats, QueryLog, User } from '../types'

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: '', label: '전체' },
  { key: 'success', label: '성공' },
  { key: 'blocked', label: '차단' },
  { key: 'error', label: '실패' },
  { key: 'chat', label: '안내' },
]

const STATUS_BADGE: Record<string, string> = {
  success: 'badge-success', blocked: 'badge-danger', error: 'badge-warning', chat: '',
}
const STATUS_LABEL: Record<string, string> = { success: '성공', blocked: '차단', error: '실패', chat: '안내' }

// 계정 승인 화면은 아직 더미 데이터 (가입 신청 API 미구현)
const DUMMY_REQUESTS = [
  { id: 1, name: '이기획', department: '기획팀', login_id: 'plan01', requested_at: '2026-10-17 10:12' },
  { id: 2, name: '최운영', department: '운영팀', login_id: 'ops_choi', requested_at: '2026-10-18 15:40' },
]

export default function AdminPage({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [status, setStatus] = useState('')
  const [stats, setStats] = useState<LogStats | null>(null)
  const [logs, setLogs] = useState<QueryLog[]>([])
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setError('')
    getLogs(status || undefined)
      .then(r => {
        setStats(r.stats)
        setLogs(r.items)
      })
      .catch(e => setError(e.message))
  }, [status])

  useEffect(() => { load() }, [load])

  const pct = (n: number) => (stats && stats.total ? `${Math.round((n / stats.total) * 100)}%` : '-')

  return (
    <div className="app-shell">
      <Header user={user} onLogout={onLogout} />
      <div className="admin-page">
        <div className="admin-inner">
          <h1>관리자 대시보드</h1>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>누가 무엇을 조회했는지, 어떤 질문이 차단됐는지 확인합니다.</p>

          <div className="kpi-grid">
            <div className="card kpi"><div className="label">전체 질문</div><div className="value">{stats?.total ?? '-'}</div></div>
            <div className="card kpi"><div className="label">오늘 질문</div><div className="value">{stats?.today ?? '-'}</div></div>
            <div className="card kpi"><div className="label">조회 성공</div><div className="value">{stats?.success ?? '-'} <span className="muted" style={{ fontSize: 13 }}>{stats && pct(stats.success)}</span></div></div>
            <div className="card kpi"><div className="label">보안 차단</div><div className="value" style={{ color: 'var(--danger)' }}>{stats?.blocked ?? '-'}</div></div>
            <div className="card kpi"><div className="label">템플릿 / LLM</div><div className="value">{stats ? `${stats.template} / ${stats.llm}` : '-'}</div></div>
          </div>

          <div className="section-head">
            <h2>조회 로그</h2>
            <div className="country-chips">
              {STATUS_FILTERS.map(f => (
                <button key={f.key} className={`country-chip ${status === f.key ? 'active' : ''}`} onClick={() => setStatus(f.key)}>{f.label}</button>
              ))}
            </div>
            <div style={{ flex: 1 }} />
            <button className="btn btn-sm" onClick={load}>새로고침</button>
          </div>
          {error && <div className="alert alert-danger">{error}</div>}
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>시각</th><th>사용자</th><th>국가</th><th>질문</th><th>생성</th><th>상태</th><th>차단/실패 사유</th><th>행</th><th>ms</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 && (
                  <tr><td colSpan={9} className="muted" style={{ textAlign: 'center', padding: 24 }}>기록이 없습니다</td></tr>
                )}
                {logs.map(l => (
                  <tr key={l.id}>
                    <td>{l.created_at}</td>
                    <td>{l.login_id}</td>
                    <td>{COUNTRY_LABEL[l.country] ?? l.country}</td>
                    <td className="question-cell" title={l.sql ?? ''}>{l.question}</td>
                    <td>{l.sql_source === 'none' ? '-' : l.sql_source === 'template' ? '템플릿' : 'LLM'}</td>
                    <td><span className={`badge ${STATUS_BADGE[l.status]}`}>{STATUS_LABEL[l.status]}</span></td>
                    <td className="question-cell" title={l.block_reason ?? ''}>{l.block_reason ?? '-'}</td>
                    <td className="num">{l.row_count ?? '-'}</td>
                    <td className="num">{l.elapsed_ms ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="section-head">
            <h2>가입 승인 대기</h2>
            <span className="badge badge-todo">더미 데이터 · 기말 구현 예정</span>
          </div>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>이름</th><th>부서</th><th>아이디</th><th>신청 시각</th><th /></tr></thead>
              <tbody>
                {DUMMY_REQUESTS.map(r => (
                  <tr key={r.id}>
                    <td>{r.name}</td><td>{r.department}</td><td>{r.login_id}</td><td>{r.requested_at}</td>
                    <td style={{ display: 'flex', gap: 6 }}>
                      <button className="btn btn-sm btn-primary" disabled>승인</button>
                      <button className="btn btn-sm" disabled>거절</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="section-head">
            <h2>감사 로그 무결성</h2>
            <span className="badge badge-todo">기말 구현 예정</span>
          </div>
          <div className="placeholder-box">
            조회 로그를 해시 체인(이전 기록의 해시를 다음 기록에 포함)으로 저장해 중간 기록이 수정·삭제되면 검증에서 바로 드러나게 할 예정.
            지금은 일반 테이블에 저장만 하는 상태.
          </div>
        </div>
      </div>
    </div>
  )
}
