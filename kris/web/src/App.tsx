import { BrowserRouter as Router, Route, Routes } from 'react-router-dom'
import AppShell from '@/components/AppShell'
import ApprovePage from '@/pages/Approve'
import AuditPage from '@/pages/Audit'
import DashboardPage from '@/pages/Dashboard'
import NotFound from '@/pages/NotFound'

export default function App() {
  return (
    <Router>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<ApprovePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Router>
  )
}
