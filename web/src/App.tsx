import { useState, useEffect } from 'react'

const API = 'http://127.0.0.1:8000'

interface Task {
  id: string
  title: string
  description: string
  risk_class: string
  autonomy_level: number
  budget: number
  status: string
  result: string | null
  created_at: string
  updated_at: string
}

interface Settings {
  autonomy_level: string
  default_budget: string
  default_risk_class: string
  provider: string
  model: string
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [health, setHealth] = useState<string>('checking...')
  const [newTitle, setNewTitle] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newRisk, setNewRisk] = useState('low')
  const [loading, setLoading] = useState(false)

  const fetchTasks = async () => {
    const res = await fetch(`${API}/api/v1/tasks`)
    setTasks(await res.json())
  }
  const fetchSettings = async () => {
    const res = await fetch(`${API}/api/v1/settings`)
    setSettings(await res.json())
  }
  const checkHealth = async () => {
    try {
      const res = await fetch(`${API}/api/v1/health`)
      const d = await res.json()
      setHealth(d.status)
    } catch {
      setHealth('offline')
    }
  }

  useEffect(() => { checkHealth(); fetchTasks(); fetchSettings() }, [])

  const createTask = async () => {
    if (!newTitle.trim()) return
    setLoading(true)
    await fetch(`${API}/api/v1/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle, description: newDesc, risk_class: newRisk, budget: 1.0 }),
    })
    setNewTitle(''); setNewDesc('')
    await fetchTasks()
    setLoading(false)
  }

  const executeTask = async (id: string) => {
    setLoading(true)
    await fetch(`${API}/api/v1/tasks/${id}/execute`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    await fetchTasks()
    setLoading(false)
  }

  const cancelTask = async (id: string) => {
    await fetch(`${API}/api/v1/tasks/${id}/cancel`, { method: 'POST' })
    await fetchTasks()
  }

  const totalTasks = tasks.length
  const completed = tasks.filter(t => t.status === 'completed').length
  const failed = tasks.filter(t => t.status === 'failed').length
  const running = tasks.filter(t => t.status === 'running').length

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1200, margin: '0 auto', padding: 20 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, borderBottom: '1px solid #e2e8f0', paddingBottom: 16 }}>
        <h1 style={{ margin: 0, color: '#1e293b' }}>CREST 1.0</h1>
        <span style={{ padding: '4px 12px', borderRadius: 12, background: health === 'ok' ? '#dcfce7' : '#fee2e2', color: health === 'ok' ? '#166534' : '#991b1b', fontSize: 14 }}>
          Backend: {health}
        </span>
      </header>

      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        {[
          { label: 'Total Tasks', value: totalTasks },
          { label: 'Completed', value: completed },
          { label: 'Failed', value: failed },
          { label: 'Running', value: running },
        ].map(c => (
          <div key={c.label} style={{ background: '#f8fafc', padding: 16, borderRadius: 8, textAlign: 'center' }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#3b82f6' }}>{c.value}</div>
            <div style={{ fontSize: 13, color: '#64748b' }}>{c.label}</div>
          </div>
        ))}
      </section>

      <section style={{ background: '#f8fafc', padding: 16, borderRadius: 8, marginBottom: 24 }}>
        <h2 style={{ marginTop: 0 }}>New Task</h2>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input placeholder="Title" value={newTitle} onChange={e => setNewTitle(e.target.value)} style={{ flex: 2, padding: 8, borderRadius: 4, border: '1px solid #cbd5e1' }} />
          <input placeholder="Description" value={newDesc} onChange={e => setNewDesc(e.target.value)} style={{ flex: 3, padding: 8, borderRadius: 4, border: '1px solid #cbd5e1' }} />
          <select value={newRisk} onChange={e => setNewRisk(e.target.value)} style={{ padding: 8, borderRadius: 4, border: '1px solid #cbd5e1' }}>
            <option value="low">Low risk</option>
            <option value="med">Medium risk</option>
            <option value="high">High risk</option>
          </select>
          <button onClick={createTask} disabled={loading} style={{ padding: '8px 16px', background: '#3b82f6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            {loading ? 'Creating...' : 'Create Task'}
          </button>
        </div>
      </section>

      <section>
        <h2>Tasks</h2>
        {tasks.length === 0 ? (
          <p style={{ color: '#94a3b8' }}>No tasks yet. Create one above.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#e2e8f0' }}>
                <th style={{ padding: 8, textAlign: 'left' }}>Title</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Risk</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Status</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Created</th>
                <th style={{ padding: 8, textAlign: 'left' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => (
                <tr key={t.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                  <td style={{ padding: 8 }}>{t.title}</td>
                  <td style={{ padding: 8 }}>
                    <span style={{ padding: '2px 8px', borderRadius: 4, background: t.risk_class === 'high' ? '#fee2e2' : t.risk_class === 'med' ? '#fef9c3' : '#dcfce7', fontSize: 12 }}>
                      {t.risk_class}
                    </span>
                  </td>
                  <td style={{ padding: 8 }}>{t.status}</td>
                  <td style={{ padding: 8, fontSize: 12, color: '#64748b' }}>{new Date(t.created_at).toLocaleString()}</td>
                  <td style={{ padding: 8 }}>
                    {t.status === 'pending' && (
                      <>
                        <button onClick={() => executeTask(t.id)} style={{ marginRight: 4, padding: '4px 8px', background: '#22c55e', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>Execute</button>
                        <button onClick={() => cancelTask(t.id)} style={{ padding: '4px 8px', background: '#ef4444', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>Cancel</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {settings && (
        <section style={{ background: '#f8fafc', padding: 16, borderRadius: 8, marginTop: 24 }}>
          <h2 style={{ marginTop: 0 }}>Settings</h2>
          <pre style={{ fontSize: 13, color: '#475569' }}>{JSON.stringify(settings, null, 2)}</pre>
        </section>
      )}
    </div>
  )
}