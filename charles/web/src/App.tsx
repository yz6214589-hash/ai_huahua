import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import AppShell from '@/components/AppShell'
import Home from '@/pages/Home'
import Jobs from '@/pages/Jobs'
import Data from '@/pages/Data'
import Watchlist from '@/pages/Watchlist'
import StockDetail from '@/pages/StockDetail'
import NotFound from '@/pages/NotFound'

export default function App() {
  return (
    <Router>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Home />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/data" element={<Data />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/stock/:code" element={<StockDetail />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Router>
  )
}
