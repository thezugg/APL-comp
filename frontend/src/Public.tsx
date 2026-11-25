import { useEffect, useState } from 'react'
import { api } from './api'
import { Bracket } from './Bracket'
import type { Competition } from './types'

export function PublicHome() {
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [error, setError] = useState('')
  useEffect(() => { api<Competition[]>('/api/public/competitions').then(setCompetitions).catch(e => setError(e.message)) }, [])
  return <main className="container main-content">
    <section className="hero"><p className="eyebrow">COMMUNITY POOL LEAGUE</p><h1>Every frame.<br/><em>Every round.</em></h1><p>Follow the draw, check the scores and see who's still standing.</p><a href="#/competitions" className="button primary">Explore competitions →</a></section>
    <div className="section-head"><div><p className="eyebrow">THE LATEST</p><h2>Knockout competitions</h2></div><span className="muted">{competitions.length} public competitions</span></div>
    {error && <div className="notice error" role="alert">{error}</div>}
    {!competitions.length && !error && <div className="empty">No draws have been published yet. Once the committee publishes one, it'll appear here.</div>}
    <div className="cards">{competitions.map(c => <a key={c.id} className="competition-card" href={`#/competition/${c.id}`}>
      <div className="card-icon">♜</div><div className="card-details"><div className="eyebrow">{c.kind.toUpperCase()} · {c.division}</div><h3>{c.name}</h3><p>{c.entry_count} entries</p></div><span className={`status ${c.status}`}>{c.status}</span><span className="card-arrow">↗</span>
    </a>)}</div>
  </main>
}

export function PublicCompetition({ id }: { id: number }) {
  const [competition, setCompetition] = useState<Competition | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    setCompetition(null); setError('')
    api<Competition>(`/api/public/competitions/${id}`).then(setCompetition).catch(e => setError(e.message))
  }, [id])
  return <main className="container main-content">
    <a className="back-link" href="#/competitions">← All competitions</a>
    {error && <div className="notice error" role="alert">{error}</div>}
    {!competition ? !error && <p className="muted">Loading bracket…</p> : <>
      <div className="detail-header"><p className="eyebrow">{competition.kind.toUpperCase()} · {competition.division}</p><h1>{competition.name}</h1><div className="meta"><span className={`status ${competition.status}`}>{competition.status}</span><span>{competition.entry_count} entries</span><span>Single elimination</span></div></div>
      <div className="section-head"><h2>Competition bracket</h2><p className="muted">Scroll sideways to follow each round →</p></div>
      <Bracket competition={competition} />
    </>}
  </main>
}
