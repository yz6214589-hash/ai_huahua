import { Navigate, Route, Routes } from 'react-router-dom'

import AppShell from './components/AppShell'
import DashboardPage from './pages/DashboardPage'
import ExecutionMonitorPage from './pages/ExecutionMonitorPage'
import LoginPage from './pages/LoginPage'
import ResearchLabPage from './pages/ResearchLabPage'
import TaskCreatePage from './pages/TaskCreatePage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/task/new" element={<TaskCreatePage />} />
        <Route path="/execution" element={<ExecutionMonitorPage />} />
        <Route path="/research" element={<ResearchLabPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}
