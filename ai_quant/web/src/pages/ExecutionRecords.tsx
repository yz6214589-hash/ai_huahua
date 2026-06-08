import { Loading } from '@/components/Loading'
import { useState, useEffect, useCallback } from 'react'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { RefreshCcw, Link, Search } from 'lucide-react'
import { useTrading } from './Execution'

/* ============================================================
 * 类型定义
 * ============================================================ */
interface OrdersResponse {
  orders: Record<string, unknown>[]
  account_type: string
}

interface TradesResponse {
  trades: Record<string, unknown>[]
  account_type: string
}

/* ============================================================
 * 字段映射表（与 ExecutionPositions 共享同一套映射规则）
 * ============================================================ */
const FIELD_LABELS: Record<string, string> = {
  stock_code: '股票代码',
  side: '方向',
  price: '价格',
  volume: '委托数量',
  quantity: '委托数量',
  status: '状态',
  order_status: '委托状态',
  order_id: '委托编号',
  order_time: '委托时间',
  trade_id: '成交编号',
  trade_time: '成交时间',
  traded_volume: '成交数量',
  traded_qty: '成交数量',
  traded_price: '成交价格',
  traded_amount: '成交金额',
  business_type: '业务类型',
  business_price: '成交价格',
  business_time: '成交时间',
  strategy_name: '策略名称',
  order_remark: '备注',
  remark: '备注',
  order_type: '委托类别',
  order_kind: '委托类别',
  cancel_info: '撤单原因',
  error_msg: '错误信息',
  market: '市场',
  account_id: '账户ID',
  account_type: '账户类型',
  session_id: '会话ID',
  create_time: '创建时间',
  update_time: '更新时间',
  cancel_time: '撤单时间',
  order_price: '委托价格',
  order_volume: '委托数量',
  traded_average_price: '成交均价',
  commission: '手续费',
  tax: '印花税',
  transfer_fee: '过户费',
}

const ORDER_STATUS_MAP: Record<string, string> = {
  '48': '未报',
  '49': '待报',
  '50': '已报',
  '51': '已报待撤',
  '52': '部成待撤',
  '53': '部撤',
  '54': '已撤',
  '55': '部成',
  '56': '已成',
  '57': '废单',
  '255': '未知',
  '未报': '未报',
  '待报': '待报',
  '已报': '已报',
  '部成': '部成',
  '部撤': '部撤',
  '已成': '已成',
  '已撤': '已撤',
  '废单': '废单',
  'order_unreported': '未报',
  'order_wait_reporting': '待报',
  'order_reported': '已报',
  'pending': '待报',
  'submitted': '已报',
  'part_traded': '部成',
  'part_cancelled': '部撤',
  'all_traded': '已成',
  'filled': '已成',
  'cancelled': '已撤',
  'invalid': '废单',
  'not_reported': '未报',
}

const ORDER_TYPE_MAP: Record<string, string> = {
  '23': '买入',
  '24': '卖出',
  '27': '融资买入',
  '28': '融券卖出',
  '29': '买券还券',
  '30': '直接还券',
  '31': '卖券还款',
  '32': '直接还款',
  '40': '专项融资买入',
  '41': '专项融券卖出',
  '42': '专项买券还券',
  '43': '专项直接还券',
  '44': '专项卖券还款',
  '45': '专项直接还款',
  '买入': '买入',
  '卖出': '卖出',
  'buy': '买入',
  'sell': '卖出',
}

const SIDE_MAP: Record<string, string> = {
  'buy': '买入',
  'sell': '卖出',
  '买入': '买入',
  '卖出': '卖出',
}

function getFieldLabel(key: string): string {
  return FIELD_LABELS[key] || key
}

function lookup(map: Record<string, string>, value: unknown): string {
  const key = String(value).trim()
  return map[key] ?? key
}

/* ============================================================
 * 主组件
 * ============================================================ */
export default function ExecutionRecords() {
  /* ----- 从 Context 获取连接状态 ----- */
  const { connectedAccount, accountId, setRefreshCallback } = useTrading()

  /* ----- 状态：委托、成交 ----- */
  const [orders, setOrders] = useState<Record<string, unknown>[]>([])
  const [trades, setTrades] = useState<Record<string, unknown>[]>([])

  const [ordersLoading, setOrdersLoading] = useState(false)
  const [tradesLoading, setTradesLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /* ----- 状态：Tab 切换 ----- */
  const [activeTab, setActiveTab] = useState<'orders' | 'trades'>('orders')

  /* ----- 状态：日期范围 ----- */
  const [startDate, setStartDate] = useState<string>(() => {
    const today = new Date()
    return today.toISOString().split('T')[0]
  })
  const [endDate, setEndDate] = useState<string>(() => {
    const today = new Date()
    return today.toISOString().split('T')[0]
  })

  /* ============================================================
   * 加载数据
   * ============================================================ */
  const loadData = useCallback(async (accountType: string, start?: string, end?: string) => {
    setError(null)
    setOrdersLoading(true)
    setTradesLoading(true)

    const dateParams = []
    if (start) dateParams.push(`start_date=${encodeURIComponent(start)}`)
    if (end) dateParams.push(`end_date=${encodeURIComponent(end)}`)
    const dateQuery = dateParams.length > 0 ? `&${dateParams.join('&')}` : ''

    const fetchOrders = fetchJson<OrdersResponse>(
      `/api/v1/trading/orders?account_type=${encodeURIComponent(accountType)}${dateQuery}`
    )
      .then(d => setOrders(d.orders || []))
      .catch(() => setOrders([]))
      .finally(() => setOrdersLoading(false))

    const fetchTrades = fetchJson<TradesResponse>(
      `/api/v1/trading/trades?account_type=${encodeURIComponent(accountType)}${dateQuery}`
    )
      .then(d => setTrades(d.trades || []))
      .catch(() => setTrades([]))
      .finally(() => setTradesLoading(false))

    await Promise.all([fetchOrders, fetchTrades])
  }, [])

  /* ============================================================
   * 连接成功后自动加载数据
   * ============================================================ */
  useEffect(() => {
    if (connectedAccount) {
      loadData(connectedAccount, startDate, endDate)
    } else {
      setOrders([])
      setTrades([])
    }
  }, [connectedAccount, startDate, endDate, loadData])

  /* ============================================================
   * 注册刷新回调给父组件
   * ============================================================ */
  useEffect(() => {
    setRefreshCallback(() => () => {
      if (connectedAccount) {
        loadData(connectedAccount, startDate, endDate)
      }
    })
    return () => setRefreshCallback(null)
  }, [connectedAccount, loadData, setRefreshCallback, startDate, endDate])

  /* ============================================================
   * 渲染：未连接提示
   * ============================================================ */
  if (!connectedAccount) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Link className="mb-3 h-8 w-8 text-zinc-300" />
        <p className="text-zinc-400">请先在上方连接账户</p>
      </div>
    )
  }

  /* ============================================================
   * 渲染：已连接 - 主界面
   * ============================================================ */
  return (
    <div className="space-y-4">
      {/* 账户提示 */}
      <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
        <span className="font-medium">当前查看账户：</span>
        <span>{connectedAccount}</span>
      </div>

      {/* 日期范围选择 */}
      <div className="flex items-center gap-4 rounded-lg border border-zinc-200 bg-white px-4 py-3">
        <span className="text-sm font-medium text-zinc-700">日期范围</span>
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
          />
          <span className="text-zinc-400">至</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="rounded-lg border border-zinc-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
          />
        </div>
        <button
          onClick={() => connectedAccount && loadData(connectedAccount, startDate, endDate)}
          disabled={ordersLoading || tradesLoading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-zinc-800 disabled:opacity-60"
        >
          <Search className="h-4 w-4" />
          查询
        </button>
      </div>

      <Card>
        <CardHeader
          right={
            <button
              onClick={() => connectedAccount && loadData(connectedAccount, startDate, endDate)}
              disabled={ordersLoading || tradesLoading}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-60"
            >
              <RefreshCcw className={`h-3.5 w-3.5 ${(ordersLoading || tradesLoading) ? 'animate-spin' : ''}`} />
              刷新
            </button>
          }
        >
          <div className="flex items-center gap-1">
            <button
              onClick={() => setActiveTab('orders')}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                activeTab === 'orders'
                  ? 'bg-zinc-900 text-white'
                  : 'text-zinc-500 hover:bg-zinc-100'
              }`}
            >
              历史委托
            </button>
            <button
              onClick={() => setActiveTab('trades')}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                activeTab === 'trades'
                  ? 'bg-zinc-900 text-white'
                  : 'text-zinc-500 hover:bg-zinc-100'
              }`}
            >
              历史成交
            </button>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          {activeTab === 'orders' && (
            ordersLoading ? (
              <Loading className="py-8" />
            ) : orders.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-zinc-400">
                暂无历史委托数据
              </div>
            ) : (
              <DynamicTable data={orders} />
            )
          )}

          {activeTab === 'trades' && (
            tradesLoading ? (
              <Loading className="py-8" />
            ) : trades.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-zinc-400">
                暂无历史成交数据
              </div>
            ) : (
              <DynamicTable data={trades} />
            )
          )}
        </CardBody>
      </Card>
    </div>
  )
}

/* ============================================================
 * 动态表格组件（增强版 - 字段中文映射）
 * ============================================================ */
function DynamicTable({ data }: { data: Record<string, unknown>[] }) {
  if (data.length === 0) return null

  const columns = Object.keys(data[0])

  function formatCell(value: unknown, column: string): string {
    if (value === null || value === undefined) return '--'

    if (column === 'side') return lookup(SIDE_MAP, String(value).toLowerCase())

    if (column === 'status' || column === 'order_status') return lookup(ORDER_STATUS_MAP, value)

    if (column === 'order_type' || column === 'order_kind') return lookup(ORDER_TYPE_MAP, value)

    if (typeof value === 'number') {
      return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2)
    }
    if (typeof value === 'boolean') return value ? '是' : '否'
    return String(value)
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-50 text-xs text-zinc-500">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-4 py-2.5 whitespace-nowrap">
                {getFieldLabel(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr key={idx} className="border-t border-zinc-100 hover:bg-zinc-50">
              {columns.map((col) => (
                <td key={col} className="px-4 py-2.5 text-zinc-700 whitespace-nowrap">
                  {formatCell(row[col], col)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
