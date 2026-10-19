import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { AUTH_EXPIRED_EVENT } from './lib/api'
import { clearAuth, getUser, isAdmin } from './lib/auth'
import type { User } from './types'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ChatPage from './pages/ChatPage'
import AdminPage from './pages/AdminPage'

function AppRoutes() {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(getUser)

  // 토큰 만료(401) → 로그인 화면으로
  useEffect(() => {
    const onExpired = () => {
      setUser(null)
      navigate('/login')
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  }, [navigate])

  const handleLogin = (u: User) => {
    setUser(u)
    navigate('/')
  }

  const handleLogout = () => {
    clearAuth()
    setUser(null)
    navigate('/login')
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage onLogin={handleLogin} />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/admin"
        element={
          !user ? <Navigate to="/login" replace />
            : isAdmin(user) ? <AdminPage user={user} onLogout={handleLogout} />
              : <Navigate to="/" replace />
        }
      />
      <Route path="/" element={user ? <ChatPage user={user} onLogout={handleLogout} /> : <Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
