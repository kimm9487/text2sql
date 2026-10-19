import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { login } from '../lib/api'
import { saveAuth } from '../lib/auth'
import type { User } from '../types'

export default function LoginPage({ onLogin }: { onLogin: (u: User) => void }) {
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(loginId.trim(), password)
      saveAuth(res.access_token, res.user)
      onLogin(res.user)
    } catch (err) {
      setError(err instanceof Error ? err.message : '로그인에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="card auth-card">
        <div className="brand">
          <span className="brand-mark">SQL</span>
          <span>Text2SQL</span>
        </div>
        <h1>로그인</h1>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          자연어로 질문하면 SQL 로 바꿔 데이터를 조회해 주는 사내 데이터 조회 도구
        </p>
        <form onSubmit={submit}>
          <label>
            아이디
            <input className="input" value={loginId} onChange={e => setLoginId(e.target.value)} autoFocus autoComplete="username" />
          </label>
          <label>
            비밀번호
            <input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <button className="btn btn-primary" style={{ height: 40 }} disabled={loading || !loginId || !password}>
            {loading ? '로그인 중…' : '로그인'}
          </button>
        </form>
        <p style={{ fontSize: 12.5, textAlign: 'center', margin: '14px 0 0' }}>
          계정이 없나요? <Link to="/register">가입 신청</Link>
        </p>
        <div className="demo-hint">
          시연용 계정 — 직원 <code>demo / demo1234</code> · 관리자 <code>admin / admin1234</code>
        </div>
      </div>
    </div>
  )
}
