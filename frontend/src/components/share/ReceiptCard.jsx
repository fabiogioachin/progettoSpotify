export default function ReceiptCard({ stats = [], title = 'Il Tuo Profilo', date }) {
  return (
    <div className="w-[320px] bg-[#f5f5f5] text-[#1a1a1a] p-6 rounded-lg" style={{ fontFamily: 'monospace' }}>
      {/* Branding */}
      <p className="text-[10px] text-[#666] text-center tracking-widest uppercase mb-3">
        Spotify Intelligence
      </p>

      {/* Title */}
      <h3 className="text-center text-lg font-bold mb-4">{title}</h3>

      {/* Dashed divider */}
      <div className="border-t border-dashed border-[#ccc] mb-4" />

      {/* Stats rows */}
      <div className="space-y-2">
        {stats.map((stat, i) => (
          <div key={i} className="flex justify-between text-sm">
            <span className="text-[#555]">{stat.label}</span>
            <span className="font-bold">{stat.value}</span>
          </div>
        ))}
      </div>

      {/* Bottom divider */}
      <div className="border-t border-dashed border-[#ccc] mt-4 pt-3">
        {date && (
          <p className="text-[10px] text-[#999] text-center">{date}</p>
        )}
      </div>
    </div>
  )
}
