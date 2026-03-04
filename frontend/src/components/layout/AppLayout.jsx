import { useLocation } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'

export default function AppLayout({ children }) {
  const { pathname } = useLocation()

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <Sidebar />
      {/* Main content area: offset by sidebar width on desktop */}
      <div className="lg:pl-60">
        <div key={pathname} className="animate-fade-in">
          {children}
        </div>
      </div>
    </div>
  )
}
