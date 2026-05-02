import { useMemo, useState } from 'react'
import { apiPost } from '../lib/api'
import type { ExecutionTaskCreate, StrategyType } from '../lib/types'

type CreateResp = { task: { id: string } & Record<string, unknown> }
type SimResp = { items: Array<{ summary: Record<string, unknown>; history: Record<string, unknown> }> }

function num(v: string, fallback: number) {
  const x = Number(v)
  return Number.isFinite(x) ? x : fallback
}

export default function TaskCreatePage() {
  const [symbol, setSymbol] = useState('510050.SH')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [totalQty, setTotalQty] = useState('100000')
  const [numSteps, setNumSteps] = useState('48')
  const [strategy, setStrategy] = useState<StrategyType>('twap')
  const [rlModelPath, setRlModelPath] = useState('ethan/models/ppo_execution.zip')
  const [eta, setEta] = useState('0.1')
  const [gamma, setGamma] = useState('0.05')
  const [adv, setAdv] = useState('')

  const [maxParticipation, setMaxParticipation] = useState('0.1')
  const [maxSingleOrder, setMaxSingleOrder] = useState('10000')
  const [cancelRetries, setCancelRetries] = useState('0')
  const [cancelWait, setCancelWait] = useState('2')
  const [slippageAlert, setSlippageAlert] = useState('50')

  const [taskId, setTaskId] = useState<string | null>(null)
  const [simSummary, setSimSummary] = useState<Record<string, unknown> | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const payload: ExecutionTaskCreate = useMemo(
    () => ({
      symbol,
      side,
      total_qty: num(totalQty, 100000),
      num_steps: num(numSteps, 48),
      strategy,
      rl_model_path: strategy === 'rl' ? rlModelPath : null,
      impact_eta: num(eta, 0.1),
      impact_gamma: num(gamma, 0.05),
      adv: adv.trim() ? num(adv, 0) : null,
      constraints: {
        max_participation_rate: num(maxParticipation, 0.1),
        max_single_order_qty: Math.max(100, Math.floor(num(maxSingleOrder, 10000))),
        cancel_retry: { max_retries: Math.max(0, Math.floor(num(cancelRetries, 0))), wait_seconds: num(cancelWait, 2) },
        slippage_alert_bps: num(slippageAlert, 50),
      },
    }),
    [
      symbol,
      side,
      totalQty,
      numSteps,
      strategy,
      rlModelPath,
      eta,
      gamma,
      adv,
      maxParticipation,
      maxSingleOrder,
      cancelRetries,
      cancelWait,
      slippageAlert,
    ],
  )

  async function createTask() {
    setBusy(true)
    setErr(null)
    setSimSummary(null)
    try {
      const res = await apiPost<CreateResp>('/api/executions', payload)
      setTaskId(res.task.id)
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function simulateOnce() {
    if (!taskId) return
    setBusy(true)
    setErr(null)
    try {
      const res = await apiPost<SimResp>(`/api/executions/${taskId}/simulate`, { n_episodes: 1 })
      const first = res.items[0]
      setSimSummary(first?.summary || null)
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function startExecution() {
    if (!taskId) return
    setBusy(true)
    setErr(null)
    try {
      await apiPost(`/api/executions/${taskId}/start`)
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="text-sm font-semibold">新建执行任务</div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
          <div className="mb-3 text-sm font-semibold">订单意图</div>
          <div className="grid grid-cols-1 gap-3">
            <div>
              <div className="text-xs text-[#9fb0d0]">标的</div>
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
            <div>
              <div className="text-xs text-[#9fb0d0]">方向</div>
              <select
                value={side}
                onChange={(e) => setSide(e.target.value as 'buy' | 'sell')}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              >
                <option value="buy">买入</option>
                <option value="sell">卖出</option>
              </select>
            </div>
            <div>
              <div className="text-xs text-[#9fb0d0]">总数量（股）</div>
              <input
                value={totalQty}
                onChange={(e) => setTotalQty(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
            <div>
              <div className="text-xs text-[#9fb0d0]">执行时段数（num_steps）</div>
              <input
                value={numSteps}
                onChange={(e) => setNumSteps(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
          <div className="mb-3 text-sm font-semibold">拆单策略与约束</div>
          <div className="grid grid-cols-1 gap-3">
            <div>
              <div className="text-xs text-[#9fb0d0]">策略类型</div>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value as StrategyType)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              >
                <option value="twap">TWAP（均匀拆分）</option>
                <option value="vwap">VWAP（U型权重）</option>
                <option value="rl">RL（加载模型执行）</option>
              </select>
            </div>

            {strategy === 'rl' ? (
              <div>
                <div className="text-xs text-[#9fb0d0]">RL 模型路径</div>
                <input
                  value={rlModelPath}
                  onChange={(e) => setRlModelPath(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
            ) : null}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[#9fb0d0]">冲击参数 eta</div>
                <input
                  value={eta}
                  onChange={(e) => setEta(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
              <div>
                <div className="text-xs text-[#9fb0d0]">冲击参数 gamma</div>
                <input
                  value={gamma}
                  onChange={(e) => setGamma(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
            </div>

            <div>
              <div className="text-xs text-[#9fb0d0]">ADV（可选：留空自动计算）</div>
              <input
                value={adv}
                onChange={(e) => setAdv(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[#9fb0d0]">最大参与率（0~1）</div>
                <input
                  value={maxParticipation}
                  onChange={(e) => setMaxParticipation(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
              <div>
                <div className="text-xs text-[#9fb0d0]">单笔上限（股）</div>
                <input
                  value={maxSingleOrder}
                  onChange={(e) => setMaxSingleOrder(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-[#9fb0d0]">撤单重试次数</div>
                <input
                  value={cancelRetries}
                  onChange={(e) => setCancelRetries(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
              <div>
                <div className="text-xs text-[#9fb0d0]">每次等待秒数</div>
                <input
                  value={cancelWait}
                  onChange={(e) => setCancelWait(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
                />
              </div>
            </div>

            <div>
              <div className="text-xs text-[#9fb0d0]">滑点阈值告警（bps）</div>
              <input
                value={slippageAlert}
                onChange={(e) => setSlippageAlert(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[#1f2c4d] bg-[#0b1530] px-3 py-2 text-sm outline-none"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-[#1f2c4d] bg-[rgba(15,26,51,.9)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-semibold">仿真预览 / 实盘执行</div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-xl border border-[#1f2c4d] px-3 py-2 text-sm"
              onClick={createTask}
              disabled={busy}
            >
              创建任务
            </button>
            <button
              type="button"
              className="rounded-xl border border-[#1f2c4d] px-3 py-2 text-sm"
              onClick={simulateOnce}
              disabled={busy || !taskId}
            >
              单次仿真
            </button>
            <button
              type="button"
              className="rounded-xl bg-[#4c7dff] px-3 py-2 text-sm font-semibold text-white"
              onClick={startExecution}
              disabled={busy || !taskId}
            >
              开始实盘执行
            </button>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-5">
          {[
            { k: '任务ID', v: taskId ?? '--' },
            { k: '到达价格', v: simSummary?.arrival_price ?? '--' },
            { k: '执行VWAP', v: simSummary?.actual_vwap ?? '--' },
            { k: '市场VWAP', v: simSummary?.market_vwap ?? '--' },
            { k: '执行缺口(bps)', v: simSummary ? Number(simSummary.implementation_shortfall) * 10000 : '--' },
          ].map((it) => (
            <div key={it.k} className="rounded-xl border border-dashed border-[#2a3b63] bg-[#0b1530] p-3">
              <div className="text-xs text-[#9fb0d0]">{it.k}</div>
              <div className="mt-1 text-sm font-extrabold">{String(it.v)}</div>
            </div>
          ))}
        </div>

        {err ? <div className="mt-3 text-xs text-[#ff4d6d]">{err}</div> : null}
      </div>
    </div>
  )
}

