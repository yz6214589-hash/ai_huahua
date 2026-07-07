import { useState, useEffect, useCallback } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { Loading } from '@/components/Loading'
import { cn } from '@/lib/utils'
import { RefreshCcw, Save, TestTube, Plug, Globe, MessageSquare, Users, Clock, Activity, Key, Wifi, WifiOff, Eye, EyeOff } from 'lucide-react'
import type { FeishuConfig, FeishuStatus } from '@/api/admin'
import { fetchFeishuConfig, updateFeishuConfig, fetchFeishuStatus, testFeishuConnection, reconnectFeishu } from '@/api/admin'

const DEFAULT_STATUS: FeishuStatus = {
  bot_status: 'offline',
  today_messages: 0,
  active_sessions: 0,
  connection_duration: '--',
  last_connect_time: '--',
}

const DEFAULT_CONFIG: FeishuConfig = {
  app_id: 'cli_xxxxxxxxxxxxxxxxxx',
  app_secret_mask: '****',
  ws_url: 'wss://msg-frontier.feishu.cn/ws/v2',
  status: 'disconnected',
}

export default function AdminFeishu() {
  const [config, setConfig] = useState<FeishuConfig>(DEFAULT_CONFIG)
  const [status, setStatus] = useState<FeishuStatus>(DEFAULT_STATUS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [showSecret, setShowSecret] = useState(false)

  // 编辑态的 App Secret (明文)
  const [appSecret, setAppSecret] = useState('')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [configData, statusData] = await Promise.all([
        fetchFeishuConfig().catch(() => DEFAULT_CONFIG),
        fetchFeishuStatus().catch(() => DEFAULT_STATUS),
      ])
      setConfig(configData)
      setStatus(statusData)
    } catch (e: any) {
      setError(e.message || '加载飞书配置失败')
      setConfig(DEFAULT_CONFIG)
      setStatus(DEFAULT_STATUS)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const updated = await updateFeishuConfig({
        app_secret: appSecret || undefined,
      })
      setConfig(updated)
      setAppSecret('')
      setSuccessMsg('飞书配置已保存')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e: any) {
      setError(`保存失败: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }, [appSecret])

  const handleTest = useCallback(async () => {
    setTesting(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const result = await testFeishuConnection()
      if (result.ok) {
        setSuccessMsg(`连接测试通过: ${result.message}`)
      } else {
        setError(`连接测试失败: ${result.message}`)
      }
      setTimeout(() => {
        setError(null)
        setSuccessMsg(null)
      }, 5000)
    } catch (e: any) {
      setError(`连接测试异常: ${e.message}`)
    } finally {
      setTesting(false)
    }
  }, [])

  const handleReconnect = useCallback(async () => {
    setReconnecting(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const result = await reconnectFeishu()
      if (result.ok) {
        setSuccessMsg(`重新连接成功: ${result.message}`)
        const newStatus = await fetchFeishuStatus().catch(() => DEFAULT_STATUS)
        setStatus(newStatus)
      } else {
        setError(`重新连接失败: ${result.message}`)
      }
      setTimeout(() => {
        setError(null)
        setSuccessMsg(null)
      }, 5000)
    } catch (e: any) {
      setError(`重新连接异常: ${e.message}`)
    } finally {
      setReconnecting(false)
    }
  }, [])

  const statsCards = [
    {
      label: '机器人状态',
      value: status.bot_status === 'online' ? '在线' : '离线',
      icon: status.bot_status === 'online' ? Wifi : WifiOff,
      color: status.bot_status === 'online' ? 'text-green-600 bg-green-50' : 'text-zinc-500 bg-zinc-50',
    },
    {
      label: '今日消息数',
      value: String(status.today_messages),
      icon: MessageSquare,
      color: 'text-blue-600 bg-blue-50',
    },
    {
      label: '活跃会话数',
      value: String(status.active_sessions),
      icon: Users,
      color: 'text-purple-600 bg-purple-50',
    },
    {
      label: '连接时长',
      value: status.connection_duration || '--',
      icon: Clock,
      color: 'text-amber-600 bg-amber-50',
    },
  ]

  if (loading) {
    return <Loading className="py-20" text="加载飞书配置..." />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-zinc-600">管理飞书机器人集成配置和连接状态</div>
        <Button variant="outline" size="sm" onClick={loadData}>
          <RefreshCcw className="mr-1 h-3.5 w-3.5" />
          刷新
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {successMsg && (
        <div className="rounded-md border border-green-200 bg-green-50 px-4 py-2 text-sm text-green-700">
          {successMsg}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {statsCards.map((card) => (
          <Card key={card.label}>
            <CardBody className="flex items-center gap-3 px-4 py-3">
              <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', card.color)}>
                <card.icon className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-zinc-900">{card.value}</span>
                  {card.label === '机器人状态' && (
                    <span className={cn(
                      'inline-block h-2 w-2 rounded-full',
                      status.bot_status === 'online' ? 'bg-green-500' : 'bg-zinc-300'
                    )} />
                  )}
                </div>
                <div className="text-xs text-zinc-500">{card.label}</div>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader
          title="连接配置"
          subtitle="配置飞书应用的连接参数"
          right={
            <div className="flex items-center gap-2">
              <Badge tone={config.status === 'connected' ? 'green' : 'zinc'}>
                {config.status === 'connected' ? '已连接' : '未连接'}
              </Badge>
            </div>
          }
        />
        <CardBody className="space-y-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1 flex items-center gap-1 text-xs font-medium text-zinc-600">
                <Key className="h-3 w-3" />
                App ID
              </label>
              <input
                value={config.app_id}
                readOnly
                className="w-full rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500"
              />
              <p className="mt-0.5 text-xs text-zinc-400">从飞书开放平台获取，当前只读</p>
            </div>
            <div>
              <label className="mb-1 flex items-center gap-1 text-xs font-medium text-zinc-600">
                <Key className="h-3 w-3" />
                App Secret
              </label>
              <div className="relative">
                <input
                  type={showSecret ? 'text' : 'password'}
                  value={appSecret || config.app_secret_mask}
                  onChange={(e) => setAppSecret(e.target.value)}
                  placeholder="输入新的 App Secret 以更新"
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 pr-8 text-sm font-mono focus:border-zinc-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowSecret((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600"
                >
                  {showSecret ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
              <p className="mt-0.5 text-xs text-zinc-400">当前值已脱敏，输入新值后可更新</p>
            </div>
            <div>
              <label className="mb-1 flex items-center gap-1 text-xs font-medium text-zinc-600">
                <Globe className="h-3 w-3" />
                WebSocket 地址
              </label>
              <input
                value={config.ws_url}
                readOnly
                className="w-full rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm font-mono text-zinc-500"
              />
              <p className="mt-0.5 text-xs text-zinc-400">飞书消息推送 WebSocket 端点，当前只读</p>
            </div>
            <div>
              <label className="mb-1 flex items-center gap-1 text-xs font-medium text-zinc-600">
                <Clock className="h-3 w-3" />
                最后连接时间
              </label>
              <input
                value={status.last_connect_time || '--'}
                readOnly
                className="w-full rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-500"
              />
              <p className="mt-0.5 text-xs text-zinc-400">最近一次成功连接的时间</p>
            </div>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="操作" subtitle="管理飞书机器人连接" />
        <CardBody>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={handleSave} disabled={saving}>
              <Save className={cn('mr-1 h-3.5 w-3.5', saving && 'animate-pulse')} />
              {saving ? '保存中...' : '保存配置'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleTest}
              disabled={testing}
            >
              <TestTube className={cn('mr-1 h-3.5 w-3.5', testing && 'animate-pulse')} />
              {testing ? '测试中...' : '测试连接'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleReconnect}
              disabled={reconnecting}
            >
              <Plug className={cn('mr-1 h-3.5 w-3.5', reconnecting && 'animate-pulse')} />
              {reconnecting ? '重连中...' : '重启连接'}
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="连接日志" subtitle="最近连接活动记录" />
        <CardBody>
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <Activity className="h-4 w-4 text-zinc-400" />
            <span>
              当前状态:
              <Badge tone={status.bot_status === 'online' ? 'green' : 'zinc'} className="ml-2">
                {status.bot_status === 'online' ? '在线' : '离线'}
              </Badge>
            </span>
            <span className="mx-2 text-zinc-300">|</span>
            <span>今日消息: {status.today_messages}</span>
            <span className="mx-2 text-zinc-300">|</span>
            <span>活跃会话: {status.active_sessions}</span>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
