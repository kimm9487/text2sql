import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { isAdmin } from '../lib/auth'
import type { User } from '../types'

interface Props {
  user: User
  onLogout: () => void
  children?: ReactNode
}

export default function Header({ user, onLogout, children }: Props) {
  const navigate = useNavigate()
  return (
    <header className="app-header">
      <button className="btn-ghost brand" style={{ border: 'none', background: 'none', cursor: 'pointer', padding: 0 }} onClick={() => navigate('/')}>
        <span className="brand-mark">SQL</span>
        <span>Text2SQL</span>
      </button>
      <span className="badge badge-warning">중간 시연 버전</span>
      <div className="header-spacer" />
      {children}
      <span className="header-user">
        <b>{user.name}</b> · {user.department} {isAdmin(user) && <span className="badge badge-accent">관리자</span>}
      </span>
      {isAdmin(user) && (
        <button className="btn btn-sm" onClick={() => navigate('/admin')}>관리자</button>
      )}
      <button className="btn btn-sm" onClick={onLogout}>로그아웃</button>
    </header>
  )
}
