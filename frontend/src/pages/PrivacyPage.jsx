import { useState } from 'react'
import { motion } from 'framer-motion'
import { Shield, Download, Trash2, Database, AlertTriangle } from 'lucide-react'
import api from '../lib/api'

// L'intercettore di `api` copre solo sessione scaduta e troppo-traffico: su un 500
// o sulla rete caduta non fa nulla. Qui il messaggio lo componiamo noi, e deve dire
// anche in che stato sono rimasti i dati — e' l'unica cosa che l'utente non puo'
// dedurre da solo.
function errorMessage(err, azione, statoDeiDati) {
  if (!err.response) {
    return `Il servizio non risponde: ${azione} non è andata a buon fine. ${statoDeiDati} Riprova fra qualche istante.`
  }
  // `detail` non e' sempre una stringa: sulle risposte scaricate come blob non
  // e' leggibile affatto, e FastAPI usa una lista sugli errori di validazione.
  const detail = err.response.data?.detail
  const causa = typeof detail === 'string' ? detail : `errore ${err.response.status}`
  return `Non è stato possibile completare ${azione} (${causa}). ${statoDeiDati}`
}

export default function PrivacyPage() {
  const [deleting, setDeleting] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  const handleExport = async () => {
    setExporting(true)
    setExportError(null)
    try {
      const response = await api.get('/api/v1/me/data/export', {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'i-miei-dati.json')
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(
        errorMessage(err, "l'esportazione", 'Nessun file è stato scaricato.')
      )
    } finally {
      setExporting(false)
    }
  }

  const handleDelete = async () => {
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.delete('/api/v1/me/data')
      window.location.href = '/'
    } catch (err) {
      // La finestra resta aperta: chiuderla qui direbbe all'utente che l'account
      // e' stato cancellato, mentre e' ancora al suo posto.
      setDeleteError(
        errorMessage(err, "l'eliminazione", 'Il tuo account e i tuoi dati sono ancora al loro posto.')
      )
      setDeleting(false)
    }
  }

  const closeConfirm = () => {
    setShowConfirm(false)
    setDeleteError(null)
  }

  const sections = [
    {
      icon: Database,
      title: 'I tuoi dati',
      content:
        'Raccogliamo i dati necessari per offrirti analisi personalizzate: ascolti recenti, artisti e brani preferiti, e statistiche aggregate sul tuo profilo musicale. Tutti i dati provengono dal tuo account Spotify tramite le API ufficiali.',
    },
    {
      icon: Shield,
      title: 'Perch\u00e9',
      content:
        'Utilizziamo i tuoi dati esclusivamente per generare analisi musicali personalizzate. Non condividiamo i tuoi dati con terze parti. Non vendiamo i tuoi dati. Non li utilizziamo per scopi pubblicitari.',
    },
    {
      icon: Database,
      title: 'Conservazione',
      content:
        'La cronologia degli ascolti viene conservata a tempo indeterminato per permetterti di analizzare le tue abitudini nel tempo. Gli snapshot giornalieri vengono mantenuti per 1 anno. La cache dei dati di popolarit\u00e0 viene aggiornata ogni 90 giorni.',
    },
    {
      icon: Shield,
      title: 'I tuoi diritti',
      content:
        'Hai il diritto di esportare tutti i tuoi dati in qualsiasi momento. Puoi eliminare il tuo account e tutti i dati associati in modo permanente e irreversibile. Queste azioni sono disponibili qui sotto.',
    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6"
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
          <Shield size={20} className="text-accent" />
        </div>
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary">
            Privacy e dati
          </h1>
          <p className="text-sm text-text-secondary">
            Come trattiamo i tuoi dati
          </p>
        </div>
      </div>

      {/* Sections */}
      <div className="space-y-4">
        {sections.map((section, i) => {
          const Icon = section.icon
          return (
            <motion.div
              key={section.title}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.05 * (i + 1) }}
              className="bg-surface rounded-xl p-6"
            >
              <div className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Icon size={16} className="text-accent" />
                </div>
                <div>
                  <h2 className="text-base font-display font-semibold text-text-primary mb-2">
                    {section.title}
                  </h2>
                  <p className="text-sm text-text-secondary leading-relaxed">
                    {section.content}
                  </p>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Actions */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.3 }}
        className="bg-surface rounded-xl p-6 space-y-4"
      >
        <h2 className="text-base font-display font-semibold text-text-primary">
          Azioni
        </h2>

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download size={16} />
            {exporting ? 'Esportazione in corso...' : 'Esporta i miei dati'}
          </button>

          <button
            onClick={() => setShowConfirm(true)}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors duration-200"
          >
            <Trash2 size={16} />
            Elimina il mio account
          </button>
        </div>

        {exportError && (
          <div
            role="alert"
            className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 flex items-start gap-2"
          >
            <AlertTriangle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-amber-400 text-sm">{exportError}</p>
          </div>
        )}
      </motion.div>

      {/* Confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => !deleting && closeConfirm()}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
            className="relative bg-surface rounded-xl p-6 max-w-sm mx-4 w-full shadow-xl"
          >
            <h3 className="text-lg font-display font-semibold text-text-primary mb-2">
              Conferma eliminazione
            </h3>
            <p className="text-sm text-text-secondary mb-6">
              Sei sicuro? Questa azione è irreversibile. Tutti i tuoi dati
              verranno eliminati permanentemente.
            </p>

            {deleteError && (
              <div
                role="alert"
                className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 mb-6 flex items-start gap-2"
              >
                <AlertTriangle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
                <p className="text-amber-400 text-sm">{deleteError}</p>
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button
                onClick={closeConfirm}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary rounded-lg hover:bg-surface-hover transition-colors duration-200 disabled:opacity-50"
              >
                Annulla
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? 'Eliminazione...' : 'Elimina tutto'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </motion.div>
  )
}
