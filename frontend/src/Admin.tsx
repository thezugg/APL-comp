import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { Bracket } from './Bracket'
import type { Auth, Competition, Division, Kind, Overview, Player, Team } from './types'

type ErrorNoticeProps = { error: string; info?: string }
function Notices({ error, info }: ErrorNoticeProps) { return <>{error && <p className="notice error" role="alert">{error}</p>}{info && <p className="notice success" role="status">{info}</p>}</> }
const kindLabels: Record<Kind, string> = { singles: 'Singles', doubles: 'Doubles', threes: 'Threes', teams: 'Teams' }

export function Admin({ auth, onLogout, route }: { auth: Auth; onLogout: () => void; route: string }) {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [divisions, setDivisions] = useState<Division[]>([])
  const [teams, setTeams] = useState<Team[]>([])
  const [players, setPlayers] = useState<Player[]>([])
  const [competitions, setCompetitions] = useState<Competition[]>([])
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)
  const section = route.split('/')[2] ?? 'overview'
  const detailId = section === 'competitions' && route.split('/')[3] ? Number(route.split('/')[3]) : null

  const refresh = useCallback(async () => {
    const [o, d, t, p, c] = await Promise.all([
      api<Overview>('/api/admin/overview'), api<Division[]>('/api/admin/divisions'),
      api<Team[]>('/api/admin/teams'), api<Player[]>('/api/admin/players'),
      api<Competition[]>('/api/admin/competitions'),
    ])
    setOverview(o); setDivisions(d); setTeams(t); setPlayers(p); setCompetitions(c)
  }, [])
  useEffect(() => { refresh().catch(e => setError((e as Error).message)) }, [refresh])

  async function action<T>(fn: () => Promise<T>, success: string, silent = false): Promise<T | undefined> {
    setError(''); setInfo(''); setBusy(true)
    try { const data = await fn(); await refresh(); if (!silent) setInfo(success); return data }
    catch (err) { setError((err as Error).message); return undefined }
    finally { setBusy(false) }
  }
  async function logout() { await action(() => api('/api/auth/logout', 'POST', {}, auth.csrf), '', true); onLogout() }
  return <main className="container main-content admin-layout">
    <div className="admin-header"><div><p className="eyebrow">COMMITTEE PORTAL</p><h1>League management</h1><p className="muted">Signed in as {auth.email}</p></div><button className="button subtle" onClick={logout}>Sign out</button></div>
    <nav className="tab-nav" aria-label="Admin sections">
      {([['overview', 'Overview'], ['members', 'Players & teams'], ['competitions', 'Competitions'], ['accounts', 'Committee']] as const).map(([id, label]) =>
        <a key={id} className={section === id ? 'selected' : ''} href={`#/admin/${id}`}>{label}</a>)}
    </nav>
    <Notices error={error} info={info}/>
    {section === 'overview' && <section><div className="stats-grid">
      {([['Players', overview?.players, '♟'], ['Teams', overview?.teams, '◈'], ['Competitions', overview?.competitions, '🏆'], ['Results to enter', overview?.pending_matches, '◷']] as const).map(([label, value, icon]) =>
        <div className="stat panel" key={label}><span className="stat-icon">{icon}</span><strong>{value ?? '…'}</strong><span>{label}</span></div>)}
      </div><div className="panel padded"><h2>Get started</h2><p className="muted">Import your player list, then create a competition and add entrants. You can preview and regenerate the random knockout draw before publishing it.</p><div className="button-row"><a className="button primary" href="#/admin/members">Manage members →</a><a className="button subtle" href="#/admin/competitions">View competitions →</a></div></div></section>}
    {section === 'members' && <Members auth={auth} divisions={divisions} teams={teams} players={players} busy={busy} action={action}/>}
    {section === 'competitions' && (detailId ?
      <CompetitionDetail key={detailId} id={detailId} auth={auth} divisions={divisions} players={players} teams={teams} busy={busy} action={action}/> :
      <Competitions auth={auth} divisions={divisions} competitions={competitions} busy={busy} action={action}/>)}
    {section === 'accounts' && <Accounts auth={auth} busy={busy} action={action}/>}
  </main>
}

type DoAction = <T>(fn: () => Promise<T>, success: string, silent?: boolean) => Promise<T | undefined>

function Members({ auth, divisions, teams, players, busy, action }: { auth: Auth; divisions: Division[]; teams: Team[]; players: Player[]; busy: boolean; action: DoAction }) {
  const [division, setDivision] = useState('')
  const [teamName, setTeamName] = useState('')
  const [teamDivision, setTeamDivision] = useState('1')
  const [playerName, setPlayerName] = useState('')
  const [playerDivision, setPlayerDivision] = useState('1')
  const [playerTeam, setPlayerTeam] = useState('')
  const [memberNumber, setMemberNumber] = useState('')
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const filtered = players.filter(p => !division || String(p.division_id) === division)
  const matchingTeams = teams.filter(t => String(t.division_id) === playerDivision)
  return <section className="form-sections">
    <div className="panel padded"><div className="section-head"><div><p className="eyebrow">SPREADSHEET IMPORT</p><h2>Import member roster</h2></div></div>
      <p className="muted">Upload UTF-8 CSV with <code>Name,Division,Team,Member ID</code>. Member ID is optional but strongly recommended so returning players can be updated safely.</p>
      <form className="form-stack" onSubmit={async e => { e.preventDefault(); if (!csvFile) return; const text = await csvFile.text(); await action(() => api('/api/admin/players/import', 'POST', text, auth.csrf), 'CSV import completed'); }}>
        <input type="file" accept=".csv,text/csv" onChange={e => setCsvFile(e.target.files?.[0] ?? null)} required/>
        <button className="button primary" disabled={busy || !csvFile}>Import CSV</button>
      </form>
    </div>
    <div className="two-col">
      <form className="panel padded form-stack" onSubmit={async e => { e.preventDefault(); const result = await action(() => api('/api/admin/teams','POST',{name: teamName, division_id: Number(teamDivision)},auth.csrf),'Team added'); if(result) setTeamName('') }}>
        <h2>Add team</h2><label>Team name<input value={teamName} onChange={e=>setTeamName(e.target.value)} required maxLength={120}/></label>
        <label>Division<select value={teamDivision} onChange={e=>setTeamDivision(e.target.value)}>{divisions.map(d=><option value={d.id} key={d.id}>{d.name}</option>)}</select></label>
        <button className="button primary" disabled={busy}>Save team</button>
      </form>
      <form className="panel padded form-stack" onSubmit={async e => { e.preventDefault(); const result = await action(() => api('/api/admin/players','POST',{name:playerName,division_id:Number(playerDivision),team_id:playerTeam?Number(playerTeam):null,member_number:memberNumber||null},auth.csrf),'Player added'); if(result){setPlayerName('');setMemberNumber('')} }}>
        <h2>Add player</h2><label>Player name<input value={playerName} onChange={e=>setPlayerName(e.target.value)} required maxLength={120}/></label>
        <label>Division<select value={playerDivision} onChange={e=>{setPlayerDivision(e.target.value);setPlayerTeam('')}}>{divisions.map(d=><option value={d.id} key={d.id}>{d.name}</option>)}</select></label>
        <label>Registered team<select value={playerTeam} onChange={e=>setPlayerTeam(e.target.value)}><option value="">No team</option>{matchingTeams.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
        <label>Member ID (optional)<input value={memberNumber} onChange={e=>setMemberNumber(e.target.value)} maxLength={80}/></label>
        <button className="button primary" disabled={busy}>Save player</button>
      </form>
    </div>
    <div className="panel padded"><div className="section-head"><h2>Registered players</h2><label className="compact-label">Division<select value={division} onChange={e=>setDivision(e.target.value)}><option value="">All divisions</option>{divisions.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label></div>
      <p className="muted">{filtered.length} players</p><div className="table-scroll"><table><thead><tr><th>Player</th><th>Division</th><th>Team</th><th>Member ID</th></tr></thead><tbody>{filtered.map(p=><tr key={p.id}><td>{p.name}</td><td>{p.division}</td><td>{p.team || 'Unassigned'}</td><td>{p.member_number || '–'}</td></tr>)}</tbody></table></div>
    </div>
  </section>
}

function Competitions({ auth, divisions, competitions, busy, action }: { auth: Auth; divisions: Division[]; competitions: Competition[]; busy: boolean; action: DoAction }) {
  const [name,setName] = useState('')
  const [kind,setKind] = useState<Kind>('singles')
  const [division,setDivision] = useState('')
  const [enforce,setEnforce] = useState(true)
  return <section className="form-sections">
    <form className="panel padded form-stack" onSubmit={async e => { e.preventDefault(); const data = await action(() => api<Competition>('/api/admin/competitions','POST',{name,kind,division_id:division?Number(division):null,enforce_same_division:enforce},auth.csrf),'Competition created'); if(data) window.location.hash=`#/admin/competitions/${data.id}` }}>
      <p className="eyebrow">NEW KNOCKOUT</p><h2>Create competition</h2><div className="form-grid">
        <label>Competition name<input value={name} onChange={e=>setName(e.target.value)} maxLength={180} placeholder="Division 2 Winter Doubles" required/></label>
        <label>Type<select value={kind} onChange={e=>setKind(e.target.value as Kind)}>{Object.entries(kindLabels).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        <label>Division<select value={division} onChange={e=>setDivision(e.target.value)}><option value="">Open / all divisions</option>{divisions.map(d=><option value={d.id} key={d.id}>{d.name}</option>)}</select></label>
        {(kind === 'doubles' || kind === 'threes') && <label className="checkbox-label"><input type="checkbox" checked={enforce} onChange={e=>setEnforce(e.target.checked)}/> Enforce same division for partners</label>}
      </div><p className="muted">Each competition starts as a private draft. Entries are selected by the committee.</p><button className="button primary" disabled={busy}>Create competition →</button>
    </form>
    <div className="panel padded"><div className="section-head"><h2>All competitions</h2><span className="muted">{competitions.length} total</span></div>
      {!competitions.length && <p className="empty">No competitions yet. Create your first one above.</p>}
      <div className="competition-list">{competitions.map(c=><a key={c.id} href={`#/admin/competitions/${c.id}`} className="competition-row"><div><strong>{c.name}</strong><p className="muted">{kindLabels[c.kind]} · {c.division} · {c.entry_count} entries</p></div><span className={`status ${c.status}`}>{c.status}</span><span>→</span></a>)}</div>
    </div>
  </section>
}

function CompetitionDetail({id,auth,divisions,players,teams,busy,action}: {id:number;auth:Auth;divisions:Division[];players:Player[];teams:Team[];busy:boolean;action:DoAction}) {
  const [competition,setCompetition] = useState<Competition | null>(null)
  const [loadError,setLoadError] = useState('')
  const [selected,setSelected] = useState<string[]>([])
  const [teamId,setTeamId] = useState('')
  const [filter,setFilter] = useState('')
  const [enforce,setEnforce] = useState(true)
  const refreshDetail = useCallback(async ()=>{ const c=await api<Competition>(`/api/admin/competitions/${id}`);setCompetition(c);setEnforce(c.enforce_same_division) },[id])
  useEffect(()=>{refreshDetail().catch(e=>setLoadError((e as Error).message))},[refreshDetail])
  const participants = competition?.entries?.flatMap(e=>e.players.map(p=>p.id)) ?? []
  const available = useMemo(() => players.filter(p=>p.active&&!participants.includes(p.id)&&(!filter||String(p.division_id)===filter)),[players,participants,filter])
  const allowed = competition?.kind === 'singles' ? 1 : competition?.kind === 'doubles' ? 2 : 3
  const relevantTeams = teams.filter(t=>!competition?.division_id||t.division_id===competition.division_id)
  if(loadError) return <div className="notice error">{loadError}</div>
  if(!competition) return <p>Loading competition…</p>
  const draft = competition.status === 'draft'
  const drawn = competition.status === 'drawn'
  const details = `${kindLabels[competition.kind]} · ${competition.division} · ${competition.entry_count} entries`
  async function mutate<T>(fn:()=>Promise<T>, message:string) { const response=await action(fn,message); if(response!==undefined) await refreshDetail(); return response }
  return <section className="form-sections">
    <a className="back-link" href="#/admin/competitions">← All competitions</a>
    <div className="detail-header"><p className="eyebrow">KNOCKOUT COMPETITION</p><h1>{competition.name}</h1><div className="meta"><span className={`status ${competition.status}`}>{competition.status}</span><span>{details}</span></div></div>
    {draft && <div className="panel padded form-stack"><div className="section-head"><h2>Competition rules</h2><span className="tag">DRAFT</span></div>
      {(competition.kind==='doubles'||competition.kind==='threes')&&<label className="checkbox-label"><input type="checkbox" checked={enforce} onChange={e=>setEnforce(e.target.checked)}/> Enforce same division for partners</label>}
      <p className="muted">Partners may play for different teams. When the switch is on, each partnership must comprise players from the same division{competition.division_id?', matching this competition':''}.</p>
      {(competition.kind==='doubles'||competition.kind==='threes') && enforce!==competition.enforce_same_division && <button disabled={busy} className="button subtle" onClick={()=>mutate(()=>api(`/api/admin/competitions/${id}/division-rule`,'PATCH',{enforce_same_division:enforce},auth.csrf),'Division rule updated')}>Save division rule</button>}
    </div>}
    {draft && <div className="panel padded form-stack"><h2>Register entries</h2>
      {competition.kind==='teams'? <form className="inline-form" onSubmit={async e=>{e.preventDefault();const r=await mutate(()=>api(`/api/admin/competitions/${id}/entries`,'POST',{team_id:Number(teamId)},auth.csrf),'Team entered');if(r)setTeamId('')}}><label>Registered team<select value={teamId} onChange={e=>setTeamId(e.target.value)} required><option value="">Choose a team</option>{relevantTeams.map(t=><option key={t.id} value={t.id}>{t.name} · {t.division}</option>)}</select></label><button className="button primary" disabled={busy||!teamId}>Add team</button></form> :
      <form className="form-stack" onSubmit={async e=>{e.preventDefault();const r=await mutate(()=>api(`/api/admin/competitions/${id}/entries`,'POST',{player_ids:selected.map(Number)},auth.csrf),'Entry registered');if(r)setSelected([])}}>
        <div className="form-grid"><label>Filter eligible players<select value={filter} onChange={e=>{setFilter(e.target.value);setSelected([])}}><option value="">All divisions</option>{divisions.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label></div>
        <div className="form-grid">{Array.from({length:allowed},(_,i)=><label key={i}>Player {i+1}<select value={selected[i]??''} onChange={e=>setSelected(old=>{const next=[...old];next[i]=e.target.value;return next})} required><option value="">Choose player</option>{available.filter(p=>!selected.includes(String(p.id))||selected[i]===String(p.id)).map(p=><option key={p.id} value={p.id}>{p.name} · {p.division} · {p.team||'No team'}</option>)}</select></label>)}</div>
        <button className="button primary" disabled={busy||Array.from({length:allowed},(_,i)=>selected[i]).some(v=>!v)}>Add {kindLabels[competition.kind]} entry</button>
      </form>}
      {competition.kind==='singles'&&competition.division_id&&<div className="button-row"><button disabled={busy} className="button subtle" onClick={()=>mutate(()=>api(`/api/admin/competitions/${id}/add-division`,'POST',{},auth.csrf),'All remaining players in this division added')}>Add entire division</button></div>}
      <p className="muted">Entries are locked once the draw is generated.</p>
    </div>}
    <div className="panel padded"><div className="section-head"><h2>Entrants</h2><span className="muted">{competition.entry_count} registered</span></div>
      {!competition.entries?.length && <p className="empty">No entries yet.</p>}
      <div className="entrant-list">{competition.entries?.map(e=><div key={e.id} className="entrant-row"><div><strong>{e.label}</strong>{e.players.length>0&&<small className="muted">{e.players.map(p=>`${p.team||'No team'} (${p.division})`).join(' · ')}</small>}</div>{draft&&<button disabled={busy} className="text-button danger-text" onClick={()=>{if(window.confirm(`Remove ${e.label}?`))mutate(()=>api(`/api/admin/competitions/${id}/entries/${e.id}`,'DELETE',undefined,auth.csrf),'Entry removed')}}>Remove</button>}</div>)}</div>
    </div>
    <div className="panel padded form-stack"><h2>Knockout draw</h2><div className="button-row">
      {(draft||drawn)&&<button className="button primary" disabled={busy||competition.entry_count<2} onClick={()=>{if(drawn&&!window.confirm('Regenerate the draft draw?'))return;mutate(()=>api(`/api/admin/competitions/${id}/draw`,'POST',{},auth.csrf),'Random draw generated')}}>{drawn?'Regenerate draw':'Generate random draw'}</button>}
      {drawn&&<button className="button primary" disabled={busy} onClick={()=>{if(window.confirm('Publish this draw? Members will be able to view it and it cannot be redrawn.'))mutate(()=>api(`/api/admin/competitions/${id}/publish`,'POST',{},auth.csrf),'Draw published')}}>Publish draw →</button>}
      {['published','completed'].includes(competition.status)&&<a className="button subtle" href={`#/competition/${id}`}>View public page ↗</a>}
    </div>
    {drawn&&<p className="muted">This draw is private until you publish it. You can regenerate it while in draft-draw status.</p>}
    <Bracket competition={competition} onScore={['published','completed'].includes(competition.status)?async (match,a,b)=>{ const res=await mutate(()=>api(`/api/admin/competitions/${id}/matches/${match.id}/result`,'POST',{score_a:a,score_b:b},auth.csrf),'Result recorded');if(res===undefined)throw new Error('Score was not saved')}:undefined}/>
    </div>
  </section>
}

function Accounts({auth,busy,action}:{auth:Auth;busy:boolean;action:DoAction}) {
  const [email,setEmail] = useState('')
  const [password,setPassword] = useState('')
  const [history,setHistory] = useState<{id:number;event:string;detail:string;created_at:string}[]>([])
  useEffect(()=>{api<typeof history>('/api/admin/audit').then(setHistory).catch(()=>{})},[])
  return <section className="form-sections"><div className="panel padded"><h2>Recent activity</h2><div className="table-scroll"><table><thead><tr><th>When</th><th>Action</th><th>Details</th></tr></thead><tbody>{history.map(h=><tr key={h.id}><td>{new Date(h.created_at).toLocaleString()}</td><td>{h.event}</td><td>{h.detail}</td></tr>)}</tbody></table></div></div>
    {auth.role==='owner'&&<form className="panel padded form-stack" onSubmit={async e=>{e.preventDefault();const result=await action(()=>api('/api/admin/users','POST',{email,password},auth.csrf),'Committee account created');if(result){setEmail('');setPassword('')}}}><h2>Add committee administrator</h2><p className="muted">Only the owner may create other administrator accounts. Share credentials securely, never through public chat.</p><label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label>Temporary password (12+ characters)<input type="password" value={password} onChange={e=>setPassword(e.target.value)} minLength={12} required/></label><button disabled={busy} className="button primary">Create administrator</button></form>}
  </section>
}
