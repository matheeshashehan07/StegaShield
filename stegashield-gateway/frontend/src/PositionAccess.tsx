import { useEffect, useState } from 'react'
import { type Api, type Profile, errorMessage } from './api'

type Position = { id: string; name: string }
type Membership = { user_id: string; position_id: string }
export function PositionAccess({ api, documentId }: { api: Api; documentId: string }) {
  const [positions, setPositions] = useState<Position[]>([])
  const [users, setUsers] = useState<Profile[]>([])
  const [members, setMembers] = useState<Membership[]>([])
  const [grants, setGrants] = useState<{ position_id: string }[]>([])
  const [version, setVersion] = useState(0)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [position, setPosition] = useState('')
  const [member, setMember] = useState('')
  const [assignment, setAssignment] = useState('')
  useEffect(() => {
    const controller = new AbortController(); setLoading(true)
    Promise.all([api.json<Position[]>('/admin/positions', { signal: controller.signal }), api.json<Profile[]>('/admin/users', { signal: controller.signal }), api.json<Membership[]>('/admin/position-memberships', { signal: controller.signal }), api.json<{ position_id: string }[]>(`/documents/${documentId}/position-permissions`, { signal: controller.signal })])
      .then(([p, u, m, g]) => { if (!controller.signal.aborted) { setPositions(p); setUsers(u); setMembers(m); setGrants(g) } })
      .catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [api, documentId, version])
  async function change(path: string, body?: object, remove = false) {
    setBusy(true); setError('')
    try { await api.request(path, { method: remove ? 'DELETE' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }); setVersion(v => v + 1); setName('') }
    catch (e) { setError(errorMessage(e)) }
    finally { setBusy(false) }
  }
  return <section className="position-access"><h3>Job-position access</h3><p className="muted">Position grants apply to all current members and future assignments. Individual grants remain independent. Each person has one job position.</p>{error && <p role="alert">{error}</p>}
    <fieldset disabled={busy || loading}><form className="grant-form" onSubmit={e => { e.preventDefault(); void change(`/documents/${documentId}/position-permissions`, { position_id: position }) }}><label>Choose a job position<select value={position} onChange={e => setPosition(e.target.value)} required><option value="">Select position</option>{positions.filter(p => !grants.some(g => g.position_id === p.id)).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><button className="primary" disabled={!position}>Grant position access</button></form>
    <ul className="permission-list">{grants.map(g => <li key={g.position_id}><strong>{positions.find(p => p.id === g.position_id)?.name || g.position_id}</strong><button onClick={() => { if (window.confirm('Revoke this position grant? Individual grants will remain.')) void change(`/documents/${documentId}/position-permissions/${g.position_id}`, undefined, true) }}>Revoke position</button></li>)}</ul>
    <details><summary>Manage job positions and member assignments</summary><p className="muted">Assignment changes affect every document granted to that position.</p><form className="grant-form" onSubmit={e => { e.preventDefault(); void change('/admin/positions', { name: name.trim() }) }}><label>New position name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} required/></label><button disabled={!name.trim()}>Create position</button></form>
    <form className="grant-form" onSubmit={e => { e.preventDefault(); if (window.confirm('Update this member’s position across all documents?')) void change(`/admin/users/${member}/position`, assignment ? { position_id: assignment } : undefined, !assignment) }}><label>Member to assign<select value={member} onChange={e => { setMember(e.target.value); setAssignment(members.find(m => m.user_id === e.target.value)?.position_id || '') }} required><option value="">Select member</option>{users.filter(u => u.role === 'user').map(u => <option key={u.id} value={u.id}>{u.display_name || u.id}</option>)}</select></label><label>Assigned position<select value={assignment} onChange={e => setAssignment(e.target.value)}><option value="">No position</option>{positions.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><button disabled={!member}>Save assignment</button></form></details></fieldset>
  </section>
}
