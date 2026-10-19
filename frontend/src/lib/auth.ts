import type { User } from '../types'

const TOKEN_KEY = 't2s_token'
const USER_KEY = 't2s_user'

// localStorage 가 막힌 환경(사생활 보호 모드 등)에서도 화면이 깨지지 않게 try/catch
function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* 저장 실패는 무시 */
  }
}

export function getToken(): string | null {
  return read(TOKEN_KEY)
}

export function getUser(): User | null {
  const raw = read(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export function saveAuth(token: string, user: User): void {
  write(TOKEN_KEY, token)
  write(USER_KEY, JSON.stringify(user))
}

export function clearAuth(): void {
  write(TOKEN_KEY, null)
  write(USER_KEY, null)
}

export function isAdmin(user: User | null): boolean {
  return user?.role === 'admin'
}
