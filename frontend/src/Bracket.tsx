import { useState } from 'react'
import type { Competition, Match, Entry } from './types'

const rounds = ['First round', 'Second round', 'Third round', 'Fourth round', 'Fifth round', 'Sixth round', 'Seventh round', 'Eighth round', 'Ninth round', 'Final']

export function Bracket({ competition, onScore }: { competition: Competition; onScore?: (match: Match, a: number, b: number) => Promise<void> }) {
  const matches = competition.matches ?? []
  const byId = new Map<number, Entry>((competition.entries ?? []).map(x => [x.id, x]))
  const maxRound = Math.max(0, ...matches.map(x => x.round_num))
  if (!matches.length) return <div className="empty">The draw hasn't been generated yet.</div>
  const label = (id: number | null) => id ? (byId.get(id)?.label ?? `Entry #${id}`) : 'To be decided'
  return <div className="bracket-scroll" aria-label="Knockout bracket">
    <div className="bracket">
      {Array.from({ length: maxRound }, (_, index) => {
        const round = index + 1
        const items = matches.filter(m => m.round_num === round)
        const title = round === maxRound ? 'Final' : round === maxRound - 1 ? 'Semi-finals' : round === maxRound - 2 ? 'Quarter-finals' : rounds[index] ?? `Round ${round}`
        return <div className="bracket-round" key={round}>
          <div className="round-title">{title} <span>{items.length} {items.length === 1 ? 'match' : 'matches'}</span></div>
          <div className="round-matches" style={{ gap: `${Math.min(22 * (2 ** index), 240)}px` }}>
            {items.map(m => <MatchCard key={m.id} match={m} label={label} onScore={onScore} />)}
          </div>
        </div>
      })}
    </div>
  </div>
}

function MatchCard({ match, label, onScore }: { match: Match; label: (id: number | null) => string; onScore?: (m: Match, a: number, b: number) => Promise<void> }) {
  const [editing, setEditing] = useState(false)
  const [a, setA] = useState(String(match.score_a ?? 0))
  const [b, setB] = useState(String(match.score_b ?? 0))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ready = !match.bye && match.a !== null && match.b !== null
  return <div className="match-card">
    <div className="match-top"><span>Match {match.position + 1}</span>{match.bye ? <span className="tag">BYE</span> : match.winner ? <span className="tag won">FINAL</span> : ready ? <span className="tag upcoming">PLAY</span> : null}</div>
    <div className={`competitor ${match.winner === match.a && match.a !== null ? 'winner' : ''}`}><span title={label(match.a)}>{label(match.a)}</span><strong>{match.score_a ?? (match.bye && match.a ? 'BYE' : '–')}</strong></div>
    <div className={`competitor ${match.winner === match.b && match.b !== null ? 'winner' : ''}`}><span title={label(match.b)}>{label(match.b)}</span><strong>{match.score_b ?? (match.bye && match.b ? 'BYE' : '–')}</strong></div>
    {onScore && ready && !editing && <button className="text-button score-toggle" onClick={() => setEditing(true)}>{match.winner ? 'Correct score' : 'Enter result'}</button>}
    {onScore && ready && editing && <form className="score-form" onSubmit={async e => {
      e.preventDefault()
      setBusy(true)
      setError('')
      try { await onScore(match, Number(a), Number(b)); setEditing(false) } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
    }}>
      <label className="sr-only" htmlFor={`sa${match.id}`}>First entrant frames</label>
      <input id={`sa${match.id}`} type="number" min="0" max="99" value={a} onChange={e => setA(e.target.value)} required />
      <span>–</span>
      <label className="sr-only" htmlFor={`sb${match.id}`}>Second entrant frames</label>
      <input id={`sb${match.id}`} type="number" min="0" max="99" value={b} onChange={e => setB(e.target.value)} required />
      <button className="button small" disabled={busy || a === b || !a || !b}>{busy ? '…' : 'Save'}</button>
      <button type="button" className="text-button" onClick={() => setEditing(false)}>Cancel</button>
      {error && <span className="notice error" role="alert">{error}</span>}
    </form>}
  </div>
}
