import { useState, useEffect, useCallback, useRef } from 'react'
import { Loading } from '@/components/Loading'
import { Card, CardBody } from '@/components/Card'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { MessageSquare, Search, Plus, RefreshCcw, MessageCircle, Bot, X, User, Sparkles, Maximize2, Minimize2, Pencil, Check, ChevronLeft, ChevronRight } from 'lucide-react'
import type { ConversationItem, ConversationStats } from '@/api/admin'
import { fetchConversations, fetchConversationStats, fetchConversationDetail, updateConversationTitle } from '@/api/admin'
import { cn } from '@/lib/utils'

interface MessageItem {
  id: string
  role: string
  content: string
  metadata: Record<string, any>
  created_at: string
}

const SOURCE_LABELS: Record<string, { label: string; tone: 'blue' | 'green' | 'zinc' }> = {
  feishu_private: { label: '飞书私聊', tone: 'blue' },
  feishu_group: { label: '飞书群聊', tone: 'green' },
  system: { label: '系统对话', tone: 'zinc' },
}

function formatDate(v: string | undefined | null): string {
  if (!v) return '--'
  const d = new Date(v)
  if (isNaN(d.getTime())) return v.slice(0, 16).replace('T', ' ')
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatFullDate(v: string | undefined | null): string {
  if (!v) return '--'
  const d = new Date(v)
  if (isNaN(d.getTime())) return v.slice(0, 19).replace('T', ' ')
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

interface ConversationDetail {
  id: string
  title: string
  source: string
  created_at: string
  updated_at: string
  messages: MessageItem[]
  messages_total: number
  messages_page: number
  messages_page_size: number
}

// 适配 API 返回的可选字段为本地必选字段
function normalizeDetail(raw: any): ConversationDetail {
  return {
    id: raw.id,
    title: raw.title,
    source: raw.source,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    messages: raw.messages || [],
    messages_total: raw.messages_total ?? raw.messages?.length ?? 0,
    messages_page: raw.messages_page ?? 1,
    messages_page_size: raw.messages_page_size ?? 20,
  }
}

// 会话详情弹窗组件
function ConversationDetailModal({
  convId,
  onClose,
  onTitleUpdated,
}: {
  convId: string
  onClose: () => void
  onTitleUpdated?: (newTitle: string) => void
}) {
  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [isFullscreen, setIsFullscreen] = useState(false)

  // 标题编辑相关状态
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [editingTitle, setEditingTitle] = useState('')
  const [savingTitle, setSavingTitle] = useState(false)

  // 滚动容器引用，用于加载上一页时保持滚动位置
  const scrollRef = useRef<HTMLDivElement>(null)
  const previousScrollHeightRef = useRef<number>(0)

  const loadPage = useCallback(async (pageToLoad: number, append: boolean = false) => {
    setLoading(true)
    setError(null)
    try {
      // 记录加载前的滚动高度（用于向上翻页时保持滚动位置）
      if (scrollRef.current) {
        previousScrollHeightRef.current = scrollRef.current.scrollHeight
      }
      const raw = await fetchConversationDetail(convId, pageToLoad, pageSize)
      const data = normalizeDetail(raw)
      setDetail((prev) => {
        if (append && prev) {
          // 上一页数据拼接到前面
          return {
            ...data,
            messages: [...data.messages, ...prev.messages],
            messages_page: pageToLoad,
          }
        }
        return data
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [convId, pageSize])

  useEffect(() => {
    loadPage(1, false)
  }, [loadPage])

  // 加载上一页后，恢复滚动位置
  useEffect(() => {
    if (page > 1 && scrollRef.current && !loading) {
      const newScrollHeight = scrollRef.current.scrollHeight
      const heightDiff = newScrollHeight - previousScrollHeightRef.current
      if (heightDiff > 0) {
        scrollRef.current.scrollTop = heightDiff
      }
    }
  }, [detail?.messages, page, loading])

  const handlePrevPage = () => {
    if (page > 1 && !loading) {
      setPage((p) => p - 1)
      loadPage(page - 1, true)
    }
  }

  const handleNextPage = () => {
    if (detail && page * pageSize < detail.messages_total && !loading) {
      setPage((p) => p + 1)
      loadPage(page + 1, false)
    }
  }

  // 标题编辑相关函数
  const startEditTitle = () => {
    if (detail) {
      setEditingTitle(detail.title)
      setIsEditingTitle(true)
    }
  }

  const cancelEditTitle = () => {
    setIsEditingTitle(false)
    setEditingTitle('')
  }

  const saveEditTitle = async () => {
    if (!detail) return
    const newTitle = editingTitle.trim()
    if (!newTitle) {
      cancelEditTitle()
      return
    }
    if (newTitle === detail.title) {
      cancelEditTitle()
      return
    }
    setSavingTitle(true)
    try {
      await updateConversationTitle(detail.id, newTitle)
      setDetail({ ...detail, title: newTitle })
      setIsEditingTitle(false)
      onTitleUpdated?.(newTitle)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSavingTitle(false)
    }
  }

  const totalPages = detail ? Math.ceil(detail.messages_total / pageSize) : 0
  const hasPrev = page > 1
  const hasNext = detail ? page * pageSize < detail.messages_total : false

  return (
    <div
      className={cn(
        'flex items-center justify-center bg-black/40',
        isFullscreen ? 'fixed inset-0 z-50' : 'fixed inset-0 z-50'
      )}
      onClick={onClose}
    >
      <div
        className={cn(
          'relative flex flex-col bg-white shadow-xl transition-all duration-200',
          isFullscreen
            ? 'h-full w-full rounded-none'
            : 'mx-4 h-[80vh] w-full max-w-3xl rounded-lg'
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4">
          <div className="flex flex-1 items-center gap-3 overflow-hidden">
            {isEditingTitle ? (
              <>
                <input
                  type="text"
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveEditTitle()
                    if (e.key === 'Escape') cancelEditTitle()
                  }}
                  disabled={savingTitle}
                  autoFocus
                  className="flex-1 rounded border border-blue-400 px-2 py-1 text-lg font-semibold text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-200"
                  placeholder="输入新标题"
                />
                <button
                  onClick={saveEditTitle}
                  disabled={savingTitle}
                  className="rounded-md p-1.5 text-emerald-600 hover:bg-emerald-50 disabled:opacity-50"
                  title="保存"
                >
                  <Check className="h-4 w-4" />
                </button>
                <button
                  onClick={cancelEditTitle}
                  disabled={savingTitle}
                  className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
                  title="取消"
                >
                  <X className="h-4 w-4" />
                </button>
              </>
            ) : (
              <>
                <h3 className="truncate text-lg font-semibold text-zinc-900" title={detail?.title}>
                  {detail?.title || '会话详情'}
                </h3>
                {detail && (
                  <button
                    onClick={startEditTitle}
                    className="rounded-md p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
                    title="重命名"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                )}
                {detail && (
                  <Badge tone={SOURCE_LABELS[detail.source]?.tone || 'zinc'}>
                    {SOURCE_LABELS[detail.source]?.label || detail.source}
                  </Badge>
                )}
              </>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
              title={isFullscreen ? '退出全屏' : '全屏'}
            >
              {isFullscreen ? <Minimize2 className="h-5 w-5" /> : <Maximize2 className="h-5 w-5" />}
            </button>
            <button
              onClick={onClose}
              className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
              title="关闭"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* 内容 */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
          {loading && !detail ? (
            <Loading size="sm" className="py-8" text="加载消息..." />
          ) : error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              加载失败: {error}
            </div>
          ) : !detail || detail.messages.length === 0 ? (
            <div className="py-8 text-center text-zinc-400">
              <MessageSquare className="mx-auto mb-2 h-6 w-6 text-zinc-300" />
              暂无消息记录
            </div>
          ) : (
            <div className="space-y-4">
              {hasPrev && (
                <div className="flex justify-center">
                  <button
                    onClick={handlePrevPage}
                    disabled={loading}
                    className="flex items-center gap-1 rounded-md border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
                  >
                    <ChevronLeft className="h-3 w-3" />
                    加载更早消息（第 {page - 1} 页）
                  </button>
                </div>
              )}
              {detail.messages.map((msg) => {
                const isUser = msg.role === 'user'
                const isAssistant = msg.role === 'assistant'
                return (
                  <div
                    key={msg.id}
                    className={cn(
                      'flex gap-3',
                      isUser ? 'flex-row-reverse' : 'flex-row'
                    )}
                  >
                    {/* 头像 */}
                    <div
                      className={cn(
                        'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                        isUser
                          ? 'bg-blue-100 text-blue-600'
                          : 'bg-emerald-100 text-emerald-600'
                      )}
                    >
                      {isUser ? (
                        <User className="h-4 w-4" />
                      ) : (
                        <Sparkles className="h-4 w-4" />
                      )}
                    </div>

                    {/* 消息内容 */}
                    <div
                      className={cn(
                        'max-w-[80%] rounded-lg px-4 py-3 text-sm',
                        isUser
                          ? 'bg-blue-50 text-zinc-800'
                          : 'bg-zinc-50 text-zinc-800'
                      )}
                    >
                      <div className="mb-1 flex items-center gap-2">
                        <span className="text-xs font-medium text-zinc-500">
                          {isUser ? '用户' : isAssistant ? 'AI助手' : msg.role}
                        </span>
                        <span className="text-xs text-zinc-400">
                          {formatFullDate(msg.created_at)}
                        </span>
                      </div>
                      <div className="whitespace-pre-wrap break-words leading-relaxed">
                        {msg.content}
                      </div>
                    </div>
                  </div>
                )
              })}
              {hasNext && (
                <div className="flex justify-center pt-2">
                  <button
                    onClick={handleNextPage}
                    disabled={loading}
                    className="flex items-center gap-1 rounded-md border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
                  >
                    加载更新消息（第 {page + 1} 页）
                    <ChevronRight className="h-3 w-3" />
                  </button>
                </div>
              )}
              {loading && detail && (
                <div className="flex justify-center py-2">
                  <Loading size="sm" text="加载中..." />
                </div>
              )}
            </div>
          )}
        </div>

        {/* 底部 */}
        {detail && (
          <div className="flex items-center justify-between border-t border-zinc-100 px-6 py-3 text-xs text-zinc-400">
            <span className="truncate">
              会话ID: {detail.id} | 消息数: {detail.messages_total}
            </span>
            <span>
              第 {page}/{totalPages || 1} 页
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function AdminConversations() {
  const [items, setItems] = useState<ConversationItem[]>([])
  const [stats, setStats] = useState<ConversationStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null)
  const pageSize = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [convData, statsData] = await Promise.all([
        fetchConversations({ search: search || undefined, source: source || undefined, page }),
        fetchConversationStats(),
      ])
      setItems(convData.items)
      setTotal(convData.total)
      setStats(statsData)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [search, source, page])

  useEffect(() => {
    load()
  }, [load])

  const handleSearch = useCallback(() => {
    setPage(1)
    load()
  }, [load])

  // 标题更新后刷新列表
  const handleTitleUpdated = useCallback((newTitle: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === selectedConvId ? { ...item, title: newTitle } : item
      )
    )
  }, [selectedConvId])

  const totalPages = Math.ceil(total / pageSize)

  const statsCards = stats
    ? [
        { label: '总会话数', value: stats.total, icon: MessageSquare, color: 'text-blue-600 bg-blue-50' },
        { label: '飞书私聊', value: stats.feishu_private, icon: MessageCircle, color: 'text-green-600 bg-green-50' },
        { label: '飞书群聊', value: stats.feishu_group, icon: MessageCircle, color: 'text-amber-600 bg-amber-50' },
        { label: '系统对话', value: stats.system, icon: Bot, color: 'text-zinc-600 bg-zinc-50' },
      ]
    : []

  return (
    <div className="space-y-4">
      {statsCards.length > 0 && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {statsCards.map((card) => (
            <Card key={card.label}>
              <CardBody className="flex items-center gap-3 px-4 py-3">
                <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', card.color)}>
                  <card.icon className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-lg font-semibold text-zinc-900">{card.value}</div>
                  <div className="text-xs text-zinc-500">{card.label}</div>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="搜索会话标题..."
              className="w-56 rounded-md border border-zinc-300 py-1.5 pl-8 pr-3 text-sm focus:border-zinc-500 focus:outline-none"
            />
          </div>
          <select
            value={source}
            onChange={(e) => { setSource(e.target.value); setPage(1) }}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-zinc-500 focus:outline-none"
          >
            <option value="">全部来源</option>
            <option value="feishu_private">飞书私聊</option>
            <option value="feishu_group">飞书群聊</option>
            <option value="system">系统对话</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCcw className="mr-1 h-3.5 w-3.5" />
            刷新
          </Button>
          <Button size="sm">
            <Plus className="mr-1 h-3.5 w-3.5" />
            新建会话
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          加载失败: {error}
        </div>
      )}

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 text-left text-xs font-medium text-zinc-500">
                <th className="px-4 py-3">标题</th>
                <th className="px-4 py-3">来源</th>
                <th className="px-4 py-3">消息数</th>
                <th className="px-4 py-3">最后消息时间</th>
                <th className="px-4 py-3">创建时间</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10">
                    <Loading size="sm" className="py-4" text="加载中..." />
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-zinc-400">
                    <MessageSquare className="mx-auto mb-2 h-6 w-6 text-zinc-300" />
                    暂无会话记录
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const src = SOURCE_LABELS[item.source] || { label: item.source, tone: 'zinc' as const }
                  return (
                    <tr key={item.id} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="max-w-xs truncate px-4 py-3 font-medium text-zinc-900">
                        <button
                          className="hover:text-blue-600"
                          title="查看会话详情"
                          onClick={() => setSelectedConvId(item.id)}
                        >
                          {item.title || '无标题'}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={src.tone}>{src.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-zinc-600">{item.message_count}</td>
                      <td className="px-4 py-3 text-zinc-500">{formatDate(item.last_message_time)}</td>
                      <td className="px-4 py-3 text-zinc-500">{formatDate(item.created_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          className="rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
                          onClick={() => setSelectedConvId(item.id)}
                        >
                          查看
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-zinc-600">
          <span>共 {total} 条记录，第 {page}/{totalPages} 页</span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="rounded border border-zinc-200 px-3 py-1 text-xs hover:bg-zinc-50 disabled:opacity-40"
            >
              上一页
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="rounded border border-zinc-200 px-3 py-1 text-xs hover:bg-zinc-50 disabled:opacity-40"
            >
              下一页
            </button>
          </div>
        </div>
      )}

      {/* 会话详情弹窗 */}
      {selectedConvId && (
        <ConversationDetailModal
          convId={selectedConvId}
          onClose={() => setSelectedConvId(null)}
          onTitleUpdated={handleTitleUpdated}
        />
      )}
    </div>
  )
}
