import { useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Header from './Header'
import Sidebar from './Sidebar'

const pageVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
  exit: { opacity: 0, y: 4, transition: { duration: 0.15, ease: 'easeIn' } },
}

export default function AppLayout({ children }) {
  const { pathname } = useLocation()

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <Sidebar />
      {/* Main content area: offset by sidebar width on desktop */}
      <div className="lg:pl-60">
        <AnimatePresence mode="wait">
          <motion.div
            key={pathname}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
