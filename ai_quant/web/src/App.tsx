/**
 * 应用主入口组件
 * 使用 React Router 定义应用的所有路由配置
 * 包含总览、数据采集、研报生成、舆情监控、执行交易、风控等主要功能模块
 */

import { BrowserRouter as Router, Navigate, Routes, Route } from 'react-router-dom'
import AppShell from '@/components/AppShell'
import Home from '@/pages/Home'
import Jobs from '@/pages/Jobs'
import JobDetail from '@/pages/JobDetail'
import Data from '@/pages/Data'
import Watchlist from '@/pages/Watchlist'
import Reports from '@/pages/Reports'
import Sentiment from '@/pages/Sentiment'
import WatchSentiment from '@/pages/WatchSentiment'
import SentimentRunDetail from '@/pages/SentimentRunDetail'
import SentimentStockDetail from '@/pages/SentimentStockDetail'
import StockDetail from '@/pages/StockDetail'
import Execution from '@/pages/Execution'
import ExecutionTasks from '@/pages/ExecutionTasks'
import ExecutionPositions from '@/pages/ExecutionPositions'
import ExecutionRecords from '@/pages/ExecutionRecords'
import Risk from '@/pages/Risk'
import RiskApprove from '@/pages/RiskApprove'
import RiskRules from '@/pages/RiskRules'
import RiskAudit from '@/pages/RiskAudit'
import Morning from '@/pages/Morning'
import Chat from '@/pages/Chat'
import InfoAccess from '@/pages/InfoAccess'
import MacroData from '@/pages/MacroData'
import FinancialHot from '@/pages/FinancialHot'
import StrategyAnalysis from '@/pages/StrategyAnalysis'
import StrategyLibrary from '@/pages/StrategyLibrary'
import StrategyInstances from '@/pages/StrategyInstances'
import StrategyBacktest from '@/pages/StrategyBacktest'
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
import NotFound from '@/pages/NotFound'

export default function App() {
  return (
    <Router>
      <Routes>
        {/* AppShell 作为布局容器，包含侧边栏和顶部栏 */}
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<Home />} />
          <Route path="/jobs" element={<Jobs />} />
          <Route path="/tasks" element={<Navigate to="/jobs" replace />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/sentiment" element={<Sentiment />} />
          <Route path="/sentiment/runs/:runId" element={<SentimentRunDetail />} />
          <Route path="/sentiment/stocks/:code" element={<SentimentStockDetail />} />
          <Route path="/data" element={<Data />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/stock/:code" element={<StockDetail />} />
          <Route path="/execution" element={<Execution />}>
            <Route index element={<Navigate to="tasks" replace />} />
            <Route path="tasks" element={<ExecutionTasks />} />
            <Route path="positions" element={<ExecutionPositions />} />
            <Route path="records" element={<ExecutionRecords />} />
          </Route>
          {/* 风控中心模块（一级导航 + Tab） */}
          <Route path="/risk" element={<Risk />}>
            <Route index element={<Navigate to="approve" replace />} />
            <Route path="approve" element={<RiskApprove />} />
            <Route path="rules" element={<RiskRules />} />
            <Route path="audit" element={<RiskAudit />} />
          </Route>
          <Route path="/morning" element={<Morning />} />
          <Route path="/briefing" element={<Navigate to="/morning" replace />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/ai" element={<Navigate to="/chat" replace />} />

          {/* 信息获取模块（一级导航 + Tab） */}
          <Route path="/info-access" element={<InfoAccess />}>
            <Route index element={<Navigate to="data-collection" replace />} />
            <Route path="data-collection" element={<Jobs />} />
            <Route path="data-collection/detail" element={<JobDetail />} />
            <Route path="sentiment" element={<WatchSentiment />} />
            <Route path="macro" element={<MacroData />} />
            <Route path="financial-hot" element={<FinancialHot />} />
          </Route>

          {/* 策略分析模块（一级导航 + Tab） */}
          <Route path="/strategy" element={<StrategyAnalysis />}>
            <Route index element={<Navigate to="library" replace />} />
            <Route path="library" element={<StrategyLibrary />} />
            <Route path="instances" element={<StrategyInstances />} />
            <Route path="backtest" element={<StrategyBacktest />} />
          </Route>

          {/* 选股模块（一级导航 + Tab） */}
          <Route path="/stock-select" element={<StockSelect />}>
            <Route index element={<Navigate to="fundamental" replace />} />
            <Route path="fundamental" element={<StockSelectFundamental />} />
            <Route path="factor" element={<StockSelectFactor />} />
            <Route path="ml" element={<StockSelectML />} />
          </Route>

          {/* 机会捕捉模块（一级导航 + Tab） */}
          <Route path="/opportunity" element={<Opportunity />}>
            <Route index element={<Navigate to="unusual" replace />} />
            <Route path="unusual" element={<OpportunityUnusual />} />
            <Route path="limitup" element={<OpportunityLimitUp />} />
            <Route path="sector" element={<OpportunitySector />} />
          </Route>

          {/* 工作流模块（一级导航 + Tab） */}
          <Route path="/workflow" element={<WorkFlow />}>
            <Route index element={<Navigate to="team" replace />} />
            <Route path="team" element={<WorkFlowTeam />} />
            <Route path="morning" element={<WorkFlowMorning />} />
            <Route path="dragon" element={<WorkFlowDragon />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Router>
  )
}
