/**
 * 应用主入口组件
 * 使用 React Router 定义应用的所有路由配置
 */

import { BrowserRouter as Router, Navigate, Routes, Route } from 'react-router-dom'
import AppShell from '@/components/AppShell'
import Home from '@/pages/Home'
import Dashboard from '@/pages/Dashboard'
import InfoAccess from '@/pages/InfoAccess'
import Jobs from '@/pages/Jobs'
import JobDetail from '@/pages/JobDetail'
import WatchSentiment from '@/pages/WatchSentiment'
import MacroData from '@/pages/MacroData'
import FinancialHot from '@/pages/FinancialHot'
import DataDelivery from '@/pages/DataDelivery'
import StockGroups from '@/pages/StockGroups'
import Watchlist from '@/pages/Watchlist'
import Reports from '@/pages/Reports'
import StockDetail from '@/pages/StockDetail'
import Execution from '@/pages/Execution'
import ExecutionTasks from '@/pages/ExecutionTasks'
import ExecutionPositions from '@/pages/ExecutionPositions'
import ExecutionRecords from '@/pages/ExecutionRecords'
import Risk from '@/pages/Risk'
import RiskApprove from '@/pages/RiskApprove'
import RiskRules from '@/pages/RiskRules'
import RiskAudit from '@/pages/RiskAudit'
import RiskDashboard from '@/pages/RiskDashboard'
import StrategyAnalysis from '@/pages/StrategyAnalysis'
import StrategyLibrary from '@/pages/StrategyLibrary'
import StrategyInstances from '@/pages/StrategyInstances'
import StrategyInstanceCreate from '@/pages/StrategyInstanceCreate'
import StrategyBacktest from '@/pages/StrategyBacktest'
import BacktestHistory from '@/pages/BacktestHistory'
import WalkForwardPanel from '@/components/WalkForwardPanel'
import ParamOptimizer from '@/pages/ParamOptimizer'
import MlTraining from '@/pages/MlTraining'
import StockSelect from '@/pages/StockSelect'
import StockSelectFundamental from '@/pages/StockSelectFundamental'
import StockSelectFactor from '@/pages/StockSelectFactor'
import StockSelectML from '@/pages/StockSelectML'
import Opportunity from '@/pages/Opportunity'
import OpportunityUnusual from '@/pages/OpportunityUnusual'
import OpportunityLimitUp from '@/pages/OpportunityLimitUp'
import OpportunitySector from '@/pages/OpportunitySector'
import WorkFlow from '@/pages/WorkFlow'
import WorkFlowTeam from '@/pages/WorkFlowTeam'
import WorkFlowMorning from '@/pages/WorkFlowMorning'
import WorkFlowDragon from '@/pages/WorkFlowDragon'
import SignalCenter from '@/pages/SignalCenter'
import PerformanceReport from '@/pages/PerformanceReport'
import PerformanceReportDetail from '@/pages/PerformanceReportDetail'
import MainForceIdentification from '@/pages/MainForceIdentification'
import SimAccount from '@/pages/SimAccount'
import NotFound from '@/pages/NotFound'
import AgentChat from '@/pages/AgentChat'

// 管理后台
import AdminLayout from '@/components/admin/AdminLayout'
import AdminConversations from '@/pages/admin/Conversations'
import AdminApiKeys from '@/pages/admin/ApiKeys'
import AdminDashboard from '@/pages/admin/Dashboard'
import AdminNotFound from '@/pages/admin/NotFound'
import AdminModels from '@/pages/admin/Models'
import AdminTools from '@/pages/admin/Tools'
import AdminPrompts from '@/pages/admin/Prompts'
import AdminAgents from '@/pages/admin/Agents'
import AdminFeishu from '@/pages/admin/Feishu'
import AdminSettings from '@/pages/admin/Settings'
import AdminMonitor from '@/pages/admin/Monitor'
import AdminScheduledJobs from '@/pages/admin/ScheduledJobs'

export default function App() {
  return (
    <Router>
      <Routes>
        {/* AI投资助手独立路由 - 不与 AppShell 集成 */}
        <Route path="/ai-chat" element={<AgentChat />} />

        {/* 管理后台独立路由 - 不与 AppShell 集成，仅通过 URL 访问 */}
        <Route path="/ai-admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="conversations" replace />} />
          <Route path="conversations" element={<AdminConversations />} />
          <Route path="models" element={<AdminModels />} />
          <Route path="tools" element={<AdminTools />} />
          <Route path="prompts" element={<AdminPrompts />} />
          <Route path="agents" element={<AdminAgents />} />
          <Route path="feishu" element={<AdminFeishu />} />
          <Route path="api-keys" element={<AdminApiKeys />} />
          <Route path="settings" element={<AdminSettings />} />
          <Route path="monitor" element={<AdminMonitor />} />
          <Route path="scheduled-jobs" element={<AdminScheduledJobs />} />
          <Route path="*" element={<AdminNotFound />} />
        </Route>

        {/* AppShell 作为布局容器，包含侧边栏和顶部栏 */}
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<Home />} />
          <Route path="/info-access" element={<InfoAccess />}>
            <Route index element={<Navigate to="data-collection" replace />} />
            <Route path="data-collection" element={<Jobs />} />
            <Route path="data-collection/detail" element={<JobDetail />} />
            <Route path="sentiment" element={<WatchSentiment />} />
            <Route path="macro" element={<MacroData />} />
            <Route path="financial-hot" element={<FinancialHot />} />
            <Route path="data-delivery" element={<DataDelivery />} />
            <Route path="stock-groups" element={<StockGroups />} />
          </Route>
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/stock/:code" element={<StockDetail />} />
          <Route path="/execution" element={<Execution />}>
            <Route index element={<Navigate to="positions" replace />} />
            <Route path="tasks" element={<ExecutionTasks />} />
            <Route path="positions" element={<ExecutionPositions />} />
            <Route path="records" element={<ExecutionRecords />} />
            <Route path="sim-account" element={<SimAccount />} />
          </Route>
          <Route path="/risk" element={<Risk />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<RiskDashboard />} />
            <Route path="mainforce" element={<MainForceIdentification />} />
            <Route path="reports" element={<Reports />} />
            <Route path="approve" element={<RiskApprove />} />
            <Route path="rules" element={<RiskRules />} />
            <Route path="audit" element={<RiskAudit />} />
          </Route>
          <Route path="/strategy" element={<StrategyAnalysis />}>
            <Route index element={<Navigate to="library" replace />} />
            <Route path="library" element={<StrategyLibrary />} />
            <Route path="instances" element={<StrategyInstances />} />
            <Route path="instances/create" element={<StrategyInstanceCreate />} />
            <Route path="backtest" element={<StrategyBacktest />} />
            <Route path="backtest-history" element={<BacktestHistory />} />
            <Route path="walk-forward" element={<WalkForwardPanel />} />
            <Route path="param-optimizer" element={<ParamOptimizer />} />
            <Route path="performance" element={<PerformanceReport />} />
            <Route path="performance/:reportId" element={<PerformanceReportDetail />} />
          </Route>
          <Route path="/ml-training" element={<MlTraining />} />
          <Route path="/stock-select" element={<StockSelect />}>
            <Route index element={<Navigate to="fundamental" replace />} />
            <Route path="fundamental" element={<StockSelectFundamental />} />
            <Route path="factor" element={<StockSelectFactor />} />
            <Route path="ml" element={<StockSelectML />} />
          </Route>
          <Route path="/opportunity" element={<Opportunity />}>
            <Route index element={<Navigate to="signals" replace />} />
            <Route path="signals" element={<SignalCenter />} />
            <Route path="unusual" element={<OpportunityUnusual />} />
            <Route path="limitup" element={<OpportunityLimitUp />} />
            <Route path="sector" element={<OpportunitySector />} />
          </Route>
          <Route path="/workflow" element={<WorkFlow />}>
            <Route index element={<Navigate to="team" replace />} />
            <Route path="team" element={<WorkFlowTeam />} />
            <Route path="morning" element={<WorkFlowMorning />} />
            <Route path="dragon" element={<WorkFlowDragon />} />
          </Route>

          <Route path="/jobs" element={<Navigate to="/info-access/data-collection" replace />} />
          <Route path="/sentiment" element={<Navigate to="/info-access/sentiment" replace />} />
          <Route path="/morning" element={<Navigate to="/workflow/morning" replace />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Router>
  )
}
