import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [ready, setReady] = useState(false)

  const signOutLocally = useCallback(() => {
    setToken('')
    setUser(null)
  }, [])

  // If any request 401s, drop straight back to the login screen.
  useEffect(() => {
    setUnauthorizedHandler(signOutLocally)
  }, [signOutLocally])

  // Restore the session on page load.
  useEffect(() => {
    if (!getToken()) {
      setReady(true)
      return
    }
    api
      .me()
      .then(setUser)
      .catch(signOutLocally)
      .finally(() => setReady(true))
  }, [signOutLocally])

  const signIn = useCallback((token, nextUser) => {
    setToken(token)
    setUser(nextUser)
  }, [])

  const signOut = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* the local session is cleared regardless */
    }
    signOutLocally()
  }, [signOutLocally])

  return (
    <AuthContext.Provider
      value={{ user, ready, signIn, signOut, isAdmin: user?.role === 'admin' }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
