import Header from './Header'
import Sidebar from './Sidebar'

export default function AppLayout({ children }) {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <Sidebar />
      {/* Main content area: offset by sidebar width on desktop */}
      <div className="lg:pl-60">
        {children}
      </div>
    </div>
  )
}
