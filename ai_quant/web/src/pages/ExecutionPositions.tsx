import { Loading } from '@/components/Loading'
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchJson } from '@/api/client'
import { Card, CardBody, CardHeader } from '@/components/Card'
import {
  Wallet, TrendingUp, TrendingDown, Clock, Link, Eye,
} from 'lucide-react'
import { useTrading } from './Execution'

/* ============================================================
 *  类型定义
 * ============================================================ */

/** 资产信息 */
interface AssetInfo {
  total_asset: number
  cash: number
  market_value: number
  frozen_cash: number
}

/** 资产接口返回 */
interface AssetResponse {
  asset: AssetInfo
  account_type: string
}

/** 持仓记录 */
interface PositionItem {
  stock_code: string
  volume: number
  can_use_volume: number
  open_price: number
  market_value: number
}

/** 持仓接口返回 */
interface PositionsResponse {
  positions: PositionItem[]
  account_type: string
}

/** 委托/成交接口返回的通用结构（字段未知，按动态字段处理） */
interface OrdersResponse {
  orders: Record<string, unknown>[]
  account_type: string
}

interface TradesResponse {
  trades: Record<string, unknown>[]
  account_type: string
}

/* ============================================================
 *  金额格式化工具
 * ============================================================ */
function fmtMoney(value: number | undefined | null): string {
  if (value == null) return '--'
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/* ============================================================
 *  主组件
 * ============================================================ */
export default function ExecutionPositions() {
  /* ----- 从 Context 获取连接状态 ----- */
  const { connectedAccount, accountId, setRefreshCallback } = useTrading()
  const navigate = useNavigate()

  /* ----- 状态：资产 / 持仓 / 委托 / 成交 ----- */
  const [asset, setAsset] = useState<AssetInfo | null>(null)
  const [positions, setPositions] = useState<PositionItem[]>([])
  const [orders, setOrders] = useState<Record<string, unknown>[]>([])
  const [trades, setTrades] = useState<Record<string, unknown>[]>([])

  const [assetLoading, setAssetLoading] = useState(false)
  const [positionsLoading, setPositionsLoading] = useState(false)
  const [ordersLoading, setOrdersLoading] = useState(false)
  const [tradesLoading, setTradesLoading] = useState(false)

  /* ----- 状态：Tab 切换 ----- */
  const [activeTab, setActiveTab] = useState<'orders' | 'trades'>('orders')

  /* ============================================================
   *  加载数据（资产 / 持仓 / 委托 / 成交）
   * ============================================================ */
  const loadData = useCallback(async (accountType: string) => {
    // 四个接口并行请求
    setAssetLoading(true)
    setPositionsLoading(true)
    setOrdersLoading(true)
    setTradesLoading(true)

    const fetchAsset = fetchJson<AssetResponse>(
      `/api/v1/trading/asset?account_type=${encodeURIComponent(accountType)}`
    )
      .then(d => setAsset(d.asset?.total_asset != null ? d.asset : null))
      .catch(() => setAsset(null))
      .finally(() => setAssetLoading(false))

    const fetchPositions = fetchJson<PositionsResponse>(
      `/api/v1/trading/positions?account_type=${encodeURIComponent(accountType)}`
    )
      .then(d => setPositions(d.positions || []))
      .catch(() => setPositions([]))
      .finally(() => setPositionsLoading(false))

    const fetchOrders = fetchJson<OrdersResponse>(
      `/api/v1/trading/orders?account_type=${encodeURIComponent(accountType)}`
    )
      .then(d => setOrders(d.orders || []))
      .catch(() => setOrders([]))
      .finally(() => setOrdersLoading(false))

    const fetchTrades = fetchJson<TradesResponse>(
      `/api/v1/trading/trades?account_type=${encodeURIComponent(accountType)}`
    )
      .then(d => setTrades(d.trades || []))
      .catch(() => setTrades([]))
      .finally(() => setTradesLoading(false))

    await Promise.all([fetchAsset, fetchPositions, fetchOrders, fetchTrades])
  }, [])

  /* ============================================================
   *  连接成功后自动加载数据
   * ============================================================ */
  useEffect(() => {
    if (connectedAccount) {
      loadData(connectedAccount)
    } else {
      // 断开连接时清空数据
      setAsset(null)
      setPositions([])
      setOrders([])
      setTrades([])
    }
  }, [connectedAccount, loadData])

  /* ============================================================
   *  注册刷新回调给父组件
   * ============================================================ */
  useEffect(() => {
    setRefreshCallback(() => () => {
      if (connectedAccount) {
        loadData(connectedAccount)
      }
    })
    return () => setRefreshCallback(null)
  }, [connectedAccount, loadData, setRefreshCallback])

  /* ============================================================
   *  渲染：未连接提示
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
   *  渲染：已连接 - 主界面
   * ============================================================ */
  return (
    <div className="space-y-4">
      {/* ----------------------------------------------------
       *  1. 资产概览卡片
       * ---------------------------------------------------- */}
      {assetLoading ? (
        <div className="flex justify-center py-8">
          <Loading className="py-2" />
        </div>
      ) : asset ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {/* 总资产 - 蓝色主题 */}
          <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
                <Wallet className="h-4 w-4 text-blue-600" />
              </div>
              <span className="text-xs font-medium text-blue-600">总资产</span>
            </div>
            <p className="text-xl font-bold text-zinc-900">{fmtMoney(asset.total_asset)}</p>
          </div>

          {/* 可用资金 - 绿色主题 */}
          <div className="rounded-lg border border-green-200 bg-green-50/50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100">
                <TrendingUp className="h-4 w-4 text-green-600" />
              </div>
              <span className="text-xs font-medium text-green-600">可用资金</span>
            </div>
            <p className="text-xl font-bold text-zinc-900">{fmtMoney(asset.cash)}</p>
          </div>

          {/* 持仓市值 - 紫色主题 */}
          <div className="rounded-lg border border-purple-200 bg-purple-50/50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100">
                <TrendingDown className="h-4 w-4 text-purple-600" />
              </div>
              <span className="text-xs font-medium text-purple-600">持仓市值</span>
            </div>
            <p className="text-xl font-bold text-zinc-900">{fmtMoney(asset.market_value)}</p>
          </div>

          {/* 冻结资金 - 灰色主题 */}
          <div className="rounded-lg border border-zinc-200 bg-zinc-50/50 p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-100">
                <Clock className="h-4 w-4 text-zinc-600" />
              </div>
              <span className="text-xs font-medium text-zinc-600">冻结资金</span>
            </div>
            <p className="text-xl font-bold text-zinc-900">{fmtMoney(asset.frozen_cash)}</p>
          </div>
        </div>
      ) : null}

      {/* ----------------------------------------------------
       *  2. 当前持仓表格
       * ---------------------------------------------------- */}
      <Card>
        <CardHeader title="当前持仓" />
        <CardBody className="p-0">
          {positionsLoading ? (
            <Loading className="py-8" />
          ) : positions.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-zinc-400">
              暂无持仓数据
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-zinc-50 text-xs text-zinc-500">
                  <tr>
                    <th className="px-4 py-2.5">股票代码</th>
                    <th className="px-4 py-2.5 text-right">持仓数量</th>
                    <th className="px-4 py-2.5 text-right">可用数量</th>
                    <th className="px-4 py-2.5 text-right">开仓均价</th>
                    <th className="px-4 py-2.5 text-right">市值</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p, idx) => (
                    <tr
                      key={`${p.stock_code}-${idx}`}
                      className="border-t border-zinc-100 hover:bg-zinc-50"
                    >
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-sm font-medium text-zinc-900">
                            {p.stock_code}
                          </span>
                          <button
                            type="button"
                            onClick={() => navigate(`/stock/${encodeURIComponent(p.stock_code)}`)}
                            className="inline-flex items-center justify-center rounded p-0.5 text-zinc-400 transition hover:bg-zinc-100 hover:text-blue-600"
                            title="查看个股详情"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-right text-zinc-700">
                        {p.volume.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-zinc-700">
                        {p.can_use_volume.toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right text-zinc-700">
                        {p.open_price.toFixed(2)}
                      </td>
                      <td className="px-4 py-2.5 text-right font-medium text-zinc-900">
                        {fmtMoney(p.market_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* ----------------------------------------------------
       *  3. Tab 切换：当日委托 / 当日成交
       * ---------------------------------------------------- */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-1">
            {/* Tab 按钮 */}
            <button
              onClick={() => setActiveTab('orders')}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                activeTab === 'orders'
                  ? 'bg-zinc-900 text-white'
                  : 'text-zinc-500 hover:bg-zinc-100'
              }`}
            >
              当日委托
            </button>
            <button
              onClick={() => setActiveTab('trades')}
              className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
                activeTab === 'trades'
                  ? 'bg-zinc-900 text-white'
                  : 'text-zinc-500 hover:bg-zinc-100'
              }`}
            >
              当日成交
            </button>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          {/* 当日委托 */}
          {activeTab === 'orders' && (
            ordersLoading ? (
              <Loading className="py-8" />
            ) : orders.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-zinc-400">
                暂无数据
              </div>
            ) : (
              <DynamicTable data={orders} />
            )
          )}

          {/* 当日成交 */}
          {activeTab === 'trades' && (
            tradesLoading ? (
              <Loading className="py-8" />
            ) : trades.length === 0 ? (
              <div className="px-6 py-12 text-center text-sm text-zinc-400">
                暂无数据
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
 *  映射表定义（集中管理所有编码映射）
 *  字段名 -> 中文、委托状态编码、委托类别编码、方向编码
 * ============================================================ */

/** 字段名 -> 中文标签映射 */
const FIELD_LABELS: Record<string, string> = {
  // 通用字段
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

/** 委托状态编码 -> 中文含义（xtquant 完整编码 48~57, 255） */
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
  // 兼容通用文本表示
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

/** 委托类别（交易操作类型）编码 -> 中文含义（xtquant 完整编码） */
const ORDER_TYPE_MAP: Record<string, string> = {
  // 股票买卖
  '23': '买入',
  '24': '卖出',
  // 信用交易
  '27': '融资买入',
  '28': '融券卖出',
  '29': '买券还券',
  '30': '直接还券',
  '31': '卖券还款',
  '32': '直接还款',
  // 专项信用交易
  '40': '专项融资买入',
  '41': '专项融券卖出',
  '42': '专项买券还券',
  '43': '专项直接还券',
  '44': '专项卖券还款',
  '45': '专项直接还款',
  // 兼容通用文本表示
  '买入': '买入',
  '卖出': '卖出',
  'buy': '买入',
  'sell': '卖出',
}

/** 方向编码 -> 中文含义 */
const SIDE_MAP: Record<string, string> = {
  'buy': '买入',
  'sell': '卖出',
  '买入': '买入',
  '卖出': '卖出',
}

/** 获取字段的中文标签，未知字段保留英文 */
function getFieldLabel(key: string): string {
  return FIELD_LABELS[key] || key
}

/** 通用映射查询：从查找表中取值，找不到返回原始字符串 */
function lookup(map: Record<string, string>, value: unknown): string {
  const key = String(value).trim()
  return map[key] ?? key
}

/* ============================================================
 *  动态表格组件
 *  根据数据第一条记录的 keys 动态生成列，英文字段名映射为中文
 * ============================================================ */
function DynamicTable({ data }: { data: Record<string, unknown>[] }) {
  if (data.length === 0) return null

  // 提取所有列名（取第一条记录的 key）
  const columns = Object.keys(data[0])

  /** 将任意值格式化为可读字符串，并做中文映射 */
  function formatCell(value: unknown, column: string): string {
    if (value === null || value === undefined) return '--'

    // 方向：buy/sell -> 买入/卖出
    if (column === 'side') return lookup(SIDE_MAP, String(value).toLowerCase())

    // 委托状态：48~57 编码 -> 中文状态
    if (column === 'status' || column === 'order_status') return lookup(ORDER_STATUS_MAP, value)

    // 委托类别：0~7 编码 -> 中文类别
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
            <tr
              key={idx}
              className="border-t border-zinc-100 hover:bg-zinc-50"
            >
              {columns.map((col) => (
                <td
                  key={col}
                  className="px-4 py-2.5 text-zinc-700 whitespace-nowrap"
                >
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
