import { createContext, useContext, useEffect, useState } from 'react'
import api from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  // Backend irraggiungibile: e' diverso da "sessione assente" e va detto all'utente.
  const [serviceDown, setServiceDown] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    checkAuth(controller.signal)
    return () => controller.abort()
  }, [])

  // Ascolta eventi 401 dalle API per invalidare la sessione senza full reload
  useEffect(() => {
    const handleExpired = () => setUser(null)
    window.addEventListener('auth:expired', handleExpired)
    return () => window.removeEventListener('auth:expired', handleExpired)
  }, [])

  async function checkAuth(signal) {
    try {
      const { data } = await api.get('/auth/me', { signal })
      setServiceDown(false)
      if (data.authenticated) {
        setUser(data.user)
      } else {
        setUser(null)
      }
    } catch (err) {
      if (err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return
      // /auth/me risponde 200 anche all'utente anonimo ({authenticated: false}),
      // quindi un errore qui non significa "sessione assente": significa che il
      // backend non ha risposto. Senza il flag l'errore moriva in console e la
      // schermata di accesso si disegnava identica al caso normale.
      console.error('Auth check failed:', err)
      setServiceDown(true)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Avvia il login OAuth, ma solo dopo aver verificato che il backend risponda.
   * `window.location.href` porta il browser fuori dalla SPA: se nessuno serve
   * /auth/spotify/login l'utente resta su una pagina bianca, senza interfaccia e
   * senza via d'uscita. Ritorna false quando il servizio non risponde, cosi' il
   * chiamante puo' restare sulla schermata di accesso e dirlo.
   */
  async function login() {
    try {
      await api.get('/auth/me', { timeout: 8000 })
    } catch (err) {
      console.error('Login interrotto, backend non raggiungibile:', err)
      setServiceDown(true)
      return false
    }
    setServiceDown(false)
    window.location.href = '/auth/spotify/login'
    return true
  }

  async function logout() {
    try {
      await api.post('/auth/logout')
    } catch (err) {
      console.warn('Logout API call failed:', err)
    }
    setUser(null)
    window.location.href = '/'
  }

  return (
    <AuthContext.Provider value={{ user, loading, serviceDown, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve essere usato dentro AuthProvider')
  return ctx
}
