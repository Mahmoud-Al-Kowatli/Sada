import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken, type User } from './api/client'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (full_name: string, email: string, password: string) => Promise<User>
  logout: () => void
}

const Ctx = createContext<AuthState>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(!!getToken())

  const loadMe = async () => {
    const { data } = await api<User>('/auth/me')
    setUser(data)
    return data
  }

  useEffect(() => {
    if (!getToken()) return
    loadMe().catch(() => setToken(null)).finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const { data } = await api<{ access_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
    setToken(data.access_token)
    return loadMe()
  }
  const register = async (full_name: string, email: string, password: string) => {
    const { data } = await api<{ access_token: string }>('/auth/register', { method: 'POST', body: JSON.stringify({ full_name, email, password }) })
    setToken(data.access_token)
    return loadMe()
  }
  const logout = () => { setToken(null); setUser(null) }

  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
