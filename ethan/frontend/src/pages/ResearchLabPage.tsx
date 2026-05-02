import { useRef, useState } from 'react'
import { apiGet, apiPost, API_BASE } from '../lib/api'

type TrainResp = { run: { id: string; status: string; model_out: string } & Record<string, unknown> }

function num(v: string, fallback: number) {
  const x = Number(v)
  return Number.isFinite(x) ? x : fallback
}

export default function ResearchLabPage() {
  const [symbol, setSymbol] = useState('510050.SH')
  const [startDate, setStartDate] = useState('2023-01-01')
  const [endDate, setEndDate] = useState('2026-04-09')
  const [totalQty, setTotalQty] = useState('100000')
  const [numSteps, setNumSteps] = useState('48')
  const [eta, setEta] = useState('0.1')
  const [gamma, setGamma] = useState('0.05')
  const [timesteps, setTimesteps] = useState('50000')
  const [modelOut, setModelOut] = useState('ethan/models/ppo_execution.zip')
  const [backtestEpisodes, setBacktestEpisodes] = useState('100')
  const [rlModelPath, setRlModelPath] = useState('ethan/models/ppo_execution.zip')

  const [runId, setRunId] = useState<string | null>(null)
  const [trainEvents, setTrainEvents] = useState<Record<string, unknown>[]>([])
  const [backtestResult, setBacktestResult] = useState<Record<string, unknown> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)

  async function train() {
    setErr(null)
    setBacktestResult(null)
    setTrainEvents([])
    try {
      const res = await apiPost<TrainResp>('/api/rl/train', {
        symbol,
        start_date: startDate,
        end_date: endDate,
        total_qty: num(totalQty, 100000),
        num_steps: num(numSteps, 48),
        impact_eta: num(eta, 0.1),
        impact_gamma: num(gamma, 0.05),
        timesteps: Math.floor(num(timesteps, 50000)),
        model_out: modelOut,
      })
      setRunId(res.run.id)
      connectWs(res.run.id)
    } catch (e) {
      setErr(String(e))
    }
  }

  function connectWs(id: string) {
    if (!id) return
    const http = API_BASE.replace(/^http/, 'ws')
    const url = `${http}/ws/rl/${id}`
    wsRef.current?.close()
    const ws = new WebSocket(url)
    wsRef.current = ws
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as Record<string, unknown>
        setTrainEvents((prev) => [...prev.slice(-300), msg])
      } catch {
        setTrainEvents((prev) => [...prev.slice(-300), { raw: ev.data }])
      }
    }
    ws.onerror = () => setErr('WebSocket 连接失败')
  }

  async function refreshRun() {
    if (!runId) return
    setErr(null)
    try {
      const res = await apiGet<{ run: Record<string, unknown> }>(`/api/rl/runs/${runId}`)
      setTrainEvents((prev) => [...prev.slice(-300), { type: 'run', data: res.run }])
    } catch (e) {
      setErr(String(e))
    }
  }

  async function runBacktest() {
    setErr(null)
    try {
      const res = await apiPost<Record<string, unknown>>('/api/rl/backtest', {
        symbol,
        start_date: startDate,
        end_date: endDate,
        total_qty: num(totalQty, 100000),
        num_steps: num(numSteps, 48),
        impact_eta: num(eta, 0.1),
        impact_gamma: num(gamma, 0.05),
        n_episodes: Math.floor(num(backtestEpisodes, 100)),
        rl_model_path: rlModelPath.trim() ? rlModelPath : null,
      })
      setBacktestResult(res)
    } catch (e) {
      setErr(String(e))
    }
  }

  return (
    <div className="space-y-4">
      <div className="text-sm font-semibold">训练与回测工作台（RL 拆单闭环）</div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
          <div className="mb-3 text-sm font-semibold">数据与环境</div>
          <div className="grid grid-cols-1 gap-3">
            <div>
              <div className="text-xs text-[#9fb0d0]">标的</div>
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[#9fb0d0]">开始日期</div>
                <input
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
              <div>
                <div className="text-xs text-[#9fb0d0]">结束日期</div>
                <input
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[#9fb0d0]">total_qty</div>
                <input
                  value={totalQty}
                  onChange={(e) => setTotalQty(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
              <div>
                <div className="text-xs text-[#9fb0d0]">num_steps</div>
                <input
                  value={numSteps}
                  onChange={(e) => setNumSteps(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[#9fb0d0]">eta</div>
                <input
                  value={eta}
                  onChange={(e) => setEta(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
              <div>
                <div className="text-xs text-[#9fb0d0]">gamma</div>
                <input
                  value={gamma}
                  onChange={(e) => setGamma(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
          <div className="mb-3 text-sm font-semibold">训练配置（PPO）</div>
          <div className="grid grid-cols-1 gap-3">
            <div>
              <div className="text-xs text-[#9fb0d0]">timesteps</div>
              <input
                value={timesteps}
                onChange={(e) => setTimesteps(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
            <div>
              <div className="text-xs text-[#9fb0d0]">模型输出路径</div>
              <input
                value={modelOut}
                onChange={(e) => setModelOut(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded-xl bg-[#4c7dff] px-3 py-2 text-sm font-semibold text-white"
                onClick={train}
              >
                开始训练
              </button>
              <button
                type="button"
                className="rounded-xl border border-[#1f2c4d] px-3 py-2 text-sm"
                onClick={refreshRun}
                disabled={!runId}
              >
                刷新训练状态
              </button>
            </div>
            <div className="rounded-xl border border-[#1f2c4d] bg-[#0b1530] p-3 text-xs text-[#9fb0d0]">
              <div>run_id：{runId ?? '--'}</div>
              <div className="mt-2 max-h-[220px] overflow-auto whitespace-pre-wrap">
                {trainEvents.length ? trainEvents.map((x, i) => <div key={i}>{JSON.stringify(x)}</div>) : '暂无训练事件'}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4 lg:col-span-2">
          <div className="mb-3 text-sm font-semibold">回测对比（TWAP / VWAP / RL）</div>
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            <div>
              <div className="text-xs text-[#9fb0d0]">n_episodes</div>
              <input
                value={backtestEpisodes}
                onChange={(e) => setBacktestEpisodes(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
            <div className="lg:col-span-2">
              <div className="text-xs text-[#9fb0d0]">RL 模型路径（可选）</div>
              <input
                value={rlModelPath}
                onChange={(e) => setRlModelPath(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded-xl bg-[#4c7dff] px-3 py-2 text-sm font-semibold text-white"
              onClick={runBacktest}
            >
              运行回测
            </button>
          </div>
          <div className="mt-3 rounded-xl border border-[#1f2c4d] bg-[#0b1530] p-3 text-xs text-[#9fb0d0]">
            {backtestResult ? JSON.stringify(backtestResult, null, 2) : '暂无回测结果'}
          </div>
        </div>
      </div>

      {err ? <div className="text-xs text-[#ff4d6d]">{err}</div> : null}
    </div>
  )
}
