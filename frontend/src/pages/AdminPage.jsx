import { useState, useEffect, useCallback } from 'react'
import { Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Users,
  Mail,
  BarChart3,
  Cog,
  RefreshCw,
  Ban,
  Copy,
  Check,
  Plus,
  Loader2,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import api from '../lib/api'

const TABS = [
  { id: 'users', label: 'Utenti', icon: Users },
  { id: 'invites', label: 'Inviti', icon: Mail },
  { id: 'api-usage', label: 'Utilizzo API', icon: BarChart3 },
  { id: 'jobs', label: 'Jobs', icon: Cog },
]

// --------------- Tab: Utenti ---------------
function UsersTab() {
  const [users, setUsers] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionLoading, setActionLoading] = useState({})

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/v1/admin/users')
      setUsers(data)
    } catch {
      setError('Errore nel caricamento degli utenti')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const handleSuspend = async (userId) => {
    if (!window.confirm('Sei sicuro di voler sospendere questo utente?')) return
    setActionLoading((prev) => ({ ...prev, [`suspend-${userId}`]: true }))
    try {
      await api.post(`/api/v1/admin/users/${userId}/suspend`)
      await fetchUsers()
    } catch {
      // interceptor handles 401/429
    } finally {
      setActionLoading((prev) => ({ ...prev, [`suspend-${userId}`]: false }))
    }
  }

  const handleForceSync = async (userId) => {
    setActionLoading((prev) => ({ ...prev, [`sync-${userId}`]: true }))
    try {
      await api.post(`/api/v1/admin/users/${userId}/force-sync`)
    } catch {
      // interceptor handles 401/429
    } finally {
      setActionLoading((prev) => ({ ...prev, [`sync-${userId}`]: false }))
    }
  }

  if (loading) return <TabSpinner />
  if (error) return <TabError message={error} onRetry={fetchUsers} />

  return (
    <div className="bg-surface rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-hover text-text-secondary text-left">
              <th className="px-4 py-3 font-medium">Nome</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Tier</th>
              <th className="px-4 py-3 font-medium">Ultimo accesso</th>
              <th className="px-4 py-3 font-medium text-right">Ascolti</th>
              <th className="px-4 py-3 font-medium text-right">Azioni</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {users?.map((u) => (
              <tr key={u.id} className="hover:bg-surface-hover/50 transition-colors">
                <td className="px-4 py-3 text-text-primary font-medium">
                  {u.display_name || '—'}
                </td>
                <td className="px-4 py-3 text-text-secondary">{u.email || '—'}</td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-accent/10 text-accent">
                    {u.tier || 'free'}
                  </span>
                </td>
                <td className="px-4 py-3 text-text-secondary">
                  {u.last_active
                    ? new Date(u.last_active).toLocaleDateString('it-IT')
                    : '—'}
                </td>
                <td className="px-4 py-3 text-text-primary text-right font-display">
                  {u.total_plays?.toLocaleString('it-IT') ?? '—'}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => handleForceSync(u.id)}
                      disabled={actionLoading[`sync-${u.id}`]}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Forza Sync"
                    >
                      {actionLoading[`sync-${u.id}`] ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <RefreshCw size={12} />
                      )}
                      Forza Sync
                    </button>
                    <button
                      onClick={() => handleSuspend(u.id)}
                      disabled={actionLoading[`suspend-${u.id}`]}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600/10 text-red-400 hover:bg-red-600/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Sospendi"
                    >
                      {actionLoading[`suspend-${u.id}`] ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Ban size={12} />
                      )}
                      Sospendi
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(!users || users.length === 0) && (
        <div className="p-8 text-center text-text-muted text-sm">
          Nessun utente trovato
        </div>
      )}
    </div>
  )
}

// --------------- Tab: Inviti ---------------
function InvitesTab() {
  const [invites, setInvites] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [creating, setCreating] = useState(false)
  const [maxUses, setMaxUses] = useState(1)
  const [copiedCode, setCopiedCode] = useState(null)

  const fetchInvites = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/v1/admin/invites')
      setInvites(data)
    } catch {
      setError('Errore nel caricamento degli inviti')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInvites()
  }, [fetchInvites])

  const handleCreate = async () => {
    setCreating(true)
    try {
      await api.post('/api/v1/admin/invites', { max_uses: maxUses })
      await fetchInvites()
    } catch {
      // interceptor handles 401/429
    } finally {
      setCreating(false)
    }
  }

  const copyInviteLink = (code) => {
    const link = `${window.location.origin}/invite/${code}`
    navigator.clipboard.writeText(link)
    setCopiedCode(code)
    setTimeout(() => setCopiedCode(null), 2000)
  }

  if (loading) return <TabSpinner />
  if (error) return <TabError message={error} onRetry={fetchInvites} />

  return (
    <div className="space-y-4">
      {/* Create invite */}
      <div className="bg-surface rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">
            Utilizzi massimi
          </label>
          <input
            type="number"
            min={1}
            max={100}
            value={maxUses}
            onChange={(e) => setMaxUses(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-24 px-3 py-2 bg-surface-hover border border-border rounded-lg text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent"
          />
        </div>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {creating ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Plus size={14} />
          )}
          Genera invito
        </button>
      </div>

      {/* Invites table */}
      <div className="bg-surface rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-surface-hover text-text-secondary text-left">
                <th className="px-4 py-3 font-medium">Codice</th>
                <th className="px-4 py-3 font-medium">Utilizzi</th>
                <th className="px-4 py-3 font-medium">Creato</th>
                <th className="px-4 py-3 font-medium">Scadenza</th>
                <th className="px-4 py-3 font-medium">Stato</th>
                <th className="px-4 py-3 font-medium text-right">Link</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {invites?.map((inv) => (
                <tr
                  key={inv.code}
                  className="hover:bg-surface-hover/50 transition-colors"
                >
                  <td className="px-4 py-3 text-text-primary font-mono text-xs">
                    {inv.code}
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {inv.uses ?? 0} / {inv.max_uses ?? '∞'}
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {inv.created_at
                      ? new Date(inv.created_at).toLocaleDateString('it-IT')
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-text-secondary">
                    {inv.expires_at
                      ? new Date(inv.expires_at).toLocaleDateString('it-IT')
                      : 'Mai'}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        inv.is_active
                          ? 'bg-green-500/10 text-green-400'
                          : 'bg-red-500/10 text-red-400'
                      }`}
                    >
                      {inv.is_active ? 'Attivo' : 'Disattivato'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {inv.is_active && (
                      <button
                        onClick={() => copyInviteLink(inv.code)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                        title="Copia link invito"
                      >
                        {copiedCode === inv.code ? (
                          <>
                            <Check size={12} />
                            Copiato
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            Copia
                          </>
                        )}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(!invites || invites.length === 0) && (
          <div className="p-8 text-center text-text-muted text-sm">
            Nessun invito generato
          </div>
        )}
      </div>
    </div>
  )
}

// --------------- Tab: Utilizzo API ---------------
function ApiUsageTab() {
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchUsage = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/v1/admin/api-usage')
      setUsage(data)
    } catch {
      setError('Errore nel caricamento dei dati di utilizzo')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchUsage()
  }, [fetchUsage])

  if (loading) return <TabSpinner />
  if (error) return <TabError message={error} onRetry={fetchUsage} />

  // Handle both array and object responses
  const usageItems = Array.isArray(usage) ? usage : usage?.users || []
  const globalStats = !Array.isArray(usage) ? usage : null

  return (
    <div className="space-y-4">
      {/* Global stats cards */}
      {globalStats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {globalStats.total_calls != null && (
            <div className="bg-surface rounded-xl p-4">
              <p className="text-xs text-text-muted mb-1">Chiamate totali</p>
              <p className="text-2xl font-display font-bold text-text-primary">
                {globalStats.total_calls.toLocaleString('it-IT')}
              </p>
            </div>
          )}
          {globalStats.budget_remaining != null && (
            <div className="bg-surface rounded-xl p-4">
              <p className="text-xs text-text-muted mb-1">Budget rimanente</p>
              <p className="text-2xl font-display font-bold text-text-primary">
                {globalStats.budget_remaining.toLocaleString('it-IT')}
              </p>
            </div>
          )}
          {globalStats.rate_limit_hits != null && (
            <div className="bg-surface rounded-xl p-4">
              <p className="text-xs text-text-muted mb-1">Rate limit raggiunti</p>
              <p className="text-2xl font-display font-bold text-text-primary">
                {globalStats.rate_limit_hits.toLocaleString('it-IT')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Per-user table */}
      {usageItems.length > 0 && (
        <div className="bg-surface rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-surface-hover text-text-secondary text-left">
                  <th className="px-4 py-3 font-medium">Utente</th>
                  <th className="px-4 py-3 font-medium text-right">Chiamate</th>
                  <th className="px-4 py-3 font-medium text-right">Ultima chiamata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {usageItems.map((item, i) => (
                  <tr
                    key={item.user_id || i}
                    className="hover:bg-surface-hover/50 transition-colors"
                  >
                    <td className="px-4 py-3 text-text-primary font-medium">
                      {item.display_name || item.user_id || '—'}
                    </td>
                    <td className="px-4 py-3 text-text-primary text-right font-display">
                      {item.call_count?.toLocaleString('it-IT') ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-text-secondary text-right">
                      {item.last_call
                        ? new Date(item.last_call).toLocaleDateString('it-IT')
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {usageItems.length === 0 && !globalStats && (
        <div className="bg-surface rounded-xl p-8 text-center text-text-muted text-sm">
          Nessun dato di utilizzo disponibile
        </div>
      )}
    </div>
  )
}

// --------------- Tab: Jobs ---------------
function JobsTab() {
  const [jobs, setJobs] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchJobs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.get('/api/v1/admin/jobs')
      setJobs(data)
    } catch {
      setError('Errore nel caricamento dei jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  if (loading) return <TabSpinner />
  if (error) return <TabError message={error} onRetry={fetchJobs} />

  const jobList = Array.isArray(jobs) ? jobs : jobs?.jobs || []

  return (
    <div className="bg-surface rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-hover text-text-secondary text-left">
              <th className="px-4 py-3 font-medium">Nome job</th>
              <th className="px-4 py-3 font-medium">Prossima esecuzione</th>
              <th className="px-4 py-3 font-medium">Stato</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {jobList.map((job, i) => (
              <tr
                key={job.id || job.name || i}
                className="hover:bg-surface-hover/50 transition-colors"
              >
                <td className="px-4 py-3 text-text-primary font-medium">
                  {job.name || job.id || '—'}
                </td>
                <td className="px-4 py-3 text-text-secondary">
                  {job.next_run_time
                    ? new Date(job.next_run_time).toLocaleString('it-IT')
                    : '—'}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      job.status === 'running' || job.pending !== false
                        ? 'bg-green-500/10 text-green-400'
                        : 'bg-yellow-500/10 text-yellow-400'
                    }`}
                  >
                    {job.status === 'running'
                      ? 'In esecuzione'
                      : job.pending === false
                        ? 'In pausa'
                        : 'Pianificato'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {jobList.length === 0 && (
        <div className="p-8 text-center text-text-muted text-sm">
          Nessun job configurato
        </div>
      )}
    </div>
  )
}

// --------------- Shared components ---------------
function TabSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <Loader2 size={24} className="animate-spin text-accent" />
    </div>
  )
}

function TabError({ message, onRetry }) {
  return (
    <div className="bg-surface rounded-xl p-8 text-center space-y-3">
      <p className="text-sm text-red-400">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 text-xs font-medium bg-accent/10 text-accent rounded-lg hover:bg-accent/20 transition-colors"
        >
          Riprova
        </button>
      )}
    </div>
  )
}

// --------------- Main AdminPage ---------------
export default function AdminPage() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('users')

  if (!user?.is_admin) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6"
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
          <Cog size={20} className="text-accent" />
        </div>
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary">
            Amministrazione
          </h1>
          <p className="text-sm text-text-secondary">
            Gestione utenti, inviti e sistema
          </p>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-2 flex-wrap">
        {TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-accent text-white'
                  : 'bg-surface-hover text-text-secondary hover:text-text-primary'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
      >
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'invites' && <InvitesTab />}
        {activeTab === 'api-usage' && <ApiUsageTab />}
        {activeTab === 'jobs' && <JobsTab />}
      </motion.div>
    </motion.div>
  )
}
