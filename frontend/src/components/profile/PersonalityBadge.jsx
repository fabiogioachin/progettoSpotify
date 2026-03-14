export default function PersonalityBadge({ personality }) {
  if (!personality) return null

  const { archetype, emoji, description, traits = [] } = personality

  return (
    <div className="bg-surface rounded-xl p-6">
      <div className="flex items-start gap-4">
        <span className="text-5xl flex-shrink-0" role="img" aria-label={archetype}>
          {emoji}
        </span>
        <div className="min-w-0">
          <h3 className="text-xl font-display font-bold text-accent">{archetype}</h3>
          <p className="text-text-secondary text-sm mt-1 leading-relaxed">{description}</p>
          {traits.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {traits.map((trait) => (
                <span
                  key={trait}
                  className="text-xs font-medium px-2.5 py-1 rounded-full bg-accent/10 text-accent"
                >
                  {trait}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
