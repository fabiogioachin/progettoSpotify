import { Users, Shuffle } from 'lucide-react'
import { StaggerContainer, StaggerItem } from '../ui/StaggerContainer'

function ComparisonItem({ item, type, icon: Icon }) {
  return (
    <div className="flex items-center gap-2.5 py-1.5">
      <Icon size={14} className="text-text-muted flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-sm text-text-primary truncate">{item.name}</p>
        {item.owner && (
          <p className="text-[11px] text-text-muted">{item.owner}</p>
        )}
      </div>
    </div>
  )
}

export default function TasteComparison({ unisce, distingue, userAName, userBName }) {
  if ((!unisce || unisce.length === 0) && (!distingue || distingue.length === 0)) {
    return null
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
      {/* Vi unisce */}
      {unisce?.length > 0 && (
        <div>
          <h4 className="text-sm font-display text-text-secondary mb-3 flex items-center gap-2">
            <Users size={14} className="text-accent" />
            Vi unisce
          </h4>
          <StaggerContainer className="space-y-0.5">
            {unisce.map((item, i) => (
              <StaggerItem key={`shared-${i}`}>
                <ComparisonItem item={item} type={item.type} icon={Users} />
              </StaggerItem>
            ))}
          </StaggerContainer>
        </div>
      )}

      {/* Vi distingue */}
      {distingue?.length > 0 && (
        <div>
          <h4 className="text-sm font-display text-text-secondary mb-3 flex items-center gap-2">
            <Shuffle size={14} className="text-accent" />
            Vi distingue
          </h4>
          <StaggerContainer className="space-y-0.5">
            {distingue.map((item, i) => (
              <StaggerItem key={`exclusive-${i}`}>
                <ComparisonItem
                  item={{
                    ...item,
                    owner: item.user === 'a' ? userAName : item.user === 'b' ? userBName : undefined,
                  }}
                  type={item.type}
                  icon={Shuffle}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>
        </div>
      )}
    </div>
  )
}
