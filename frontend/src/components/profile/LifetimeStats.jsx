import { Headphones, Users, Music, Activity } from 'lucide-react'
import KPICard from '../cards/KPICard'
import { StaggerContainer, StaggerItem } from '../ui/StaggerContainer'

export default function LifetimeStats({ metrics }) {
  if (!metrics) return null

  const cards = [
    {
      title: 'Ascolti Totali',
      value: metrics.total_plays_lifetime ?? 0,
      icon: Headphones,
      tooltip: 'Numero totale di riproduzioni registrate dal tuo account',
    },
    {
      title: 'Artisti Unici',
      value: metrics.total_artists_lifetime ?? 0,
      icon: Users,
      tooltip: 'Quanti artisti diversi hai ascoltato in totale',
    },
    {
      title: 'Brani Unici',
      value: metrics.total_tracks_lifetime ?? 0,
      icon: Music,
      tooltip: 'Quanti brani diversi hai riprodotto in totale',
    },
    {
      title: 'Consistenza',
      value: metrics.listening_consistency ?? 0,
      suffix: '%',
      icon: Activity,
      tooltip: 'Quanto ascolti regolarmente: 100% = tutti i giorni',
    },
  ]

  return (
    <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, i) => (
        <StaggerItem key={card.title}>
          <KPICard {...card} delay={i * 100} />
        </StaggerItem>
      ))}
    </StaggerContainer>
  )
}
