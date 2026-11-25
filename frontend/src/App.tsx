import { useEffect, useState } from 'react'
import { api } from './api'
import type { Auth } from './types'
import "./styles.css"
import { PublicHome, PublicCompetition } from './Public'
import { Admin } from './Admin'

function useRoute() {
  const [route, setRoute] = useState(window.location.hash || '#/')
  useEffect(() => {
    const update = () => setRoute(window.location.hash || '#/')
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  return route
}

export default function App() {
  const route = useRoute()
  const [auth, setAuth] = useState<Auth | null>(null)
  const [checked, setChecked] = useState(false)
  useEffect(() => { api<Auth>('/api/auth/me').then(setAuth).catch(() => {}).finally(() => setChecked(true)) }, [])
  const onAdmin = route.startsWith('#/admin')
  const publicMatch = route.match(/^#\/competition\/(\d+)/)
  return <>
    <header className="site-header"><div className="container topbar"><a className="brand" href="#/"><span className="brand-mark">🎱</span><span>POOL<span className="brand-accent">LEAGUE</span><small>COMPETITION MANAGER</small></span></a><nav aria-label="Main navigation"><a className={!onAdmin ? 'active' : ''} href="#/competitions">Competitions</a><a className={onAdmin ? 'active' : ''} href="#/admin">{auth ? 'Committee dashboard' : 'Committee login'}</a></nav></div></header>
    {onAdmin ? !checked ? <main className="container main-content">Loading…</main> : auth ? <Admin key={auth.id} auth={auth} onLogout={() => { setAuth(null); window.location.hash = '#/' }} route={route} /> : <Login onLogin={setAuth} /> : publicMatch ? <PublicCompetition id={Number(publicMatch[1])} /> : <PublicHome />}
    <footer className="site-footer"><div className="container"><span>Pool League Competition Manager</span><span>Built for grassroots pool 🎱</span></div></footer>
  </>
}

function Login({ onLogin }: { onLogin: (auth: Auth) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return <main className="container main-content"><div className="login-panel panel"><p className="eyebrow">RESTRICTED ACCESS</p><h1>Committee sign in</h1><p className="muted">Manage members, entries, knockout draws and results.</p>
    <form className="form-stack" onSubmit={async e => {
      e.preventDefault(); setError(''); setBusy(true)
      try { const result = await api<Auth>('/api/auth/login', 'POST', { email, password }); onLogin(result) }
      catch (err) { setError((err as Error).message) } finally { setBusy(false) }
    }}>
      <label>Email address<input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required /></label>
      <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
      {error && <div className="notice error" role="alert">{error}</div>}
      <button className="button primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in →'}</button>
    </form>
  </div></main>
}
