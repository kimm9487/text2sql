import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

// 가입 신청 화면 — 화면만 먼저 만들어 둔 상태.
// TODO(기말): /api/auth/register 연동 → 관리자 승인 후 계정 생성
export default function RegisterPage() {
  const [submitted, setSubmitted] = useState(false)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
  }

  return (
    <div className="auth-page">
      <div className="card auth-card">
        <div className="brand">
          <span className="brand-mark">SQL</span>
          <span>Text2SQL</span>
        </div>
        <h1>가입 신청 <span className="badge badge-todo">기말 구현 예정</span></h1>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          신청하면 관리자가 승인한 뒤 로그인할 수 있습니다.
        </p>
        <form onSubmit={submit}>
          <label>부서<input className="input" placeholder="예: 마케팅팀" /></label>
          <label>이름<input className="input" /></label>
          <label>이메일<input className="input" type="email" /></label>
          <label>아이디<input className="input" /></label>
          <label>비밀번호<input className="input" type="password" /></label>
          {submitted && (
            <div className="notice">
              가입 신청·관리자 승인 기능은 아직 서버와 연결되지 않았습니다 (기말 구현 예정). 시연은 로그인 화면의 데모 계정을 이용해 주세요.
            </div>
          )}
          <button className="btn btn-primary" style={{ height: 40 }}>신청하기</button>
        </form>
        <p style={{ fontSize: 12.5, textAlign: 'center', margin: '14px 0 0' }}>
          <Link to="/login">로그인으로 돌아가기</Link>
        </p>
      </div>
    </div>
  )
}
