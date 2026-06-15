import { cn } from '@/lib/utils'
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Plus,
  Search,
  Trash2,
  Pencil,
  X,
  Send,
  User,
  MoreVertical,
  MessageSquare,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchJson } from '@/api/client'

// ===== 类型定义 =====
interface MessageItem {
  id: string
  role: string
  content: string
  metadata: Record<string, any>
  created_at: string
}

interface ConversationItem {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

// ===== 工具函数 =====
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// ===== 会话列表组件 =====
function ConversationList({
  conversations,
  selectedId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  collapsed,
  onToggleCollapse,
}: {
  conversations: ConversationItem[]
  selectedId: string | null
  onSelect: (id: string) => void
  onCreate: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  collapsed: boolean
  onToggleCollapse: () => void
}) {
  const [search, setSearch] = useState('')
  const [menu, setMenu] = useState<{
    x: number
    y: number
    convId: string
    title: string
  } | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingTitle, setEditingTitle] = useState('')

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )

  const closeMenu = () => setMenu(null)

  const startRename = (id: string, title: string) => {
    setEditingId(id)
    setEditingTitle(title)
    closeMenu()
  }

  const saveRename = () => {
    if (editingId && editingTitle.trim()) {
      onRename(editingId, editingTitle.trim())
    }
    setEditingId(null)
    setEditingTitle('')
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditingTitle('')
  }

  return (
    <div className="flex h-full flex-col border-r border-zinc-200 bg-zinc-50/80">
      {/* 头部：标题 + 新建 */}
      <div className="flex items-center justify-between border-b border-zinc-200/60 px-2.5 py-2">
        <span className="text-xs font-semibold text-zinc-500">会话列表</span>
        <button
          onClick={onCreate}
          className="flex h-6 w-6 items-center justify-center rounded-md bg-zinc-900 text-white transition hover:bg-zinc-700"
          title="新建会话"
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* 搜索框 */}
      <div className="border-b border-zinc-200/60 p-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索..."
            className="w-full rounded-md border border-zinc-200 bg-white py-1.5 pl-7 pr-2 text-xs text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-400 focus:outline-none"
          />
        </div>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto py-1">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 text-zinc-400">
            <MessageSquare className="mb-1 h-5 w-5" />
            <span className="text-xs">暂无会话</span>
          </div>
        ) : (
          filtered.map((conv) => (
            <div
              key={conv.id}
              className={cn(
                'group relative flex cursor-pointer items-center gap-1.5 px-2.5 py-2 transition',
                selectedId === conv.id
                  ? 'bg-white shadow-sm'
                  : 'hover:bg-white/60'
              )}
              onClick={() => onSelect(conv.id)}
              onContextMenu={(e) => {
                e.preventDefault()
                setMenu({ x: e.clientX, y: e.clientY, convId: conv.id, title: conv.title })
              }}
            >
              {editingId === conv.id ? (
                <div className="flex flex-1 items-center gap-1">
                  <input
                    type="text"
                    value={editingTitle}
                    onChange={(e) => setEditingTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveRename()
                      if (e.key === 'Escape') cancelRename()
                    }}
                    onClick={(e) => e.stopPropagation()}
                    autoFocus
                    className="flex-1 rounded border border-blue-400 px-1.5 py-0.5 text-xs text-zinc-900 focus:outline-none"
                  />
                </div>
              ) : (
                <>
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-zinc-500">
                    <Bot className="h-3 w-3" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="truncate text-xs font-medium text-zinc-800">
                      {conv.title || '新对话'}
                    </div>
                    <div className="truncate text-[10px] text-zinc-400">
                      {conv.message_count} 条 · {formatDate(conv.updated_at)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setMenu({
                        x: e.clientX,
                        y: e.clientY,
                        convId: conv.id,
                        title: conv.title,
                      })
                    }}
                    className="opacity-0 rounded p-0.5 text-zinc-400 transition group-hover:opacity-100 hover:bg-zinc-100"
                  >
                    <MoreVertical className="h-3 w-3" />
                  </button>
                </>
              )}
            </div>
          ))
        )}
      </div>

      {/* 右键菜单 */}
      {menu && (
        <>
          <div className="fixed inset-0 z-[60]" onClick={closeMenu} />
          <div
            className="fixed z-[70] w-28 overflow-hidden rounded-lg border border-zinc-200 bg-white py-1 shadow-lg"
            style={{ left: menu.x, top: menu.y }}
          >
            <button
              onClick={() => startRename(menu.convId, menu.title)}
              className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-xs text-zinc-700 hover:bg-zinc-50"
            >
              <Pencil className="h-3 w-3" />
              重命名
            </button>
            <button
              onClick={() => {
                onDelete(menu.convId)
                closeMenu()
              }}
              className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50"
            >
              <Trash2 className="h-3 w-3" />
              删除
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// ===== 消息输入组件 =====
function MessageInput({
  onSend,
  disabled,
}: {
  onSend: (content: string) => void
  disabled: boolean
}) {
  const [input, setInput] = useState('')

  const handleSend = () => {
    const content = input.trim()
    if (content && !disabled) {
      onSend(content)
      setInput('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-zinc-200 p-2.5">
      <div className="flex items-end gap-2">
        <div className="flex-1 rounded-xl border border-zinc-200 bg-white px-3 py-2 shadow-sm transition focus-within:border-zinc-400 focus-within:ring-1 focus-within:ring-zinc-100">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题..."
            rows={1}
            disabled={disabled}
            className="w-full resize-none bg-transparent text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-none"
            style={{ minHeight: '20px', maxHeight: '80px' }}
          />
        </div>
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition',
            disabled || !input.trim()
              ? 'bg-zinc-100 text-zinc-400 cursor-not-allowed'
              : 'bg-zinc-900 text-white hover:bg-zinc-800'
          )}
          title="发送"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

// ===== 消息列表组件 =====
function MessageList({
  messages,
  loading,
}: {
  messages: MessageItem[]
  loading: boolean
}) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3">
      {messages.length === 0 && !loading ? (
        <div className="flex flex-col items-center justify-center py-10 text-zinc-400">
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-zinc-100">
            <Bot className="h-5 w-5 text-zinc-400" />
          </div>
          <h3 className="mb-1 text-sm font-semibold text-zinc-700">AI 投资助手</h3>
          <p className="mb-4 text-xs text-zinc-400">有什么可以帮您的？</p>
          <div className="w-full space-y-1.5 px-2">
            {['生成今日晨会简报', '分析贵州茅台投资价值', '最近有哪些热门板块？', '推荐低估值蓝筹股'].map(
              (q) => (
                <div
                  key={q}
                  className="cursor-pointer rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2 text-xs text-zinc-600 transition hover:border-zinc-200 hover:bg-white"
                >
                  {q}
                </div>
              )
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {messages.map((msg) => {
            const isUser = msg.role === 'user'
            return (
              <div
                key={msg.id}
                className={cn('flex gap-2', isUser ? 'flex-row-reverse' : 'flex-row')}
              >
                <div
                  className={cn(
                    'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                    isUser ? 'bg-blue-100 text-blue-600' : 'bg-emerald-100 text-emerald-600'
                  )}
                >
                  {isUser ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
                </div>
                <div
                  className={cn(
                    'max-w-[78%] rounded-lg px-2.5 py-2 text-xs leading-relaxed',
                    isUser
                      ? 'bg-blue-50 text-zinc-800 rounded-br-sm'
                      : 'bg-zinc-50 text-zinc-800 rounded-bl-sm'
                  )}
                >
                  <div className="mb-0.5 flex items-center gap-1.5">
                    <span className="text-[10px] font-medium text-zinc-500">
                      {isUser ? '你' : 'AI'}
                    </span>
                    <span className="text-[10px] text-zinc-400">{formatTime(msg.created_at)}</span>
                  </div>
                  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                </div>
              </div>
            )
          })}
          {loading && (
            <div className="flex justify-center py-3">
              <div className="flex items-center gap-1">
                <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400" />
                <div
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400"
                  style={{ animationDelay: '0.1s' }}
                />
                <div
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400"
                  style={{ animationDelay: '0.2s' }}
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ===== 主组件 =====
export function AssistantDrawer() {
  const [collapsed, setCollapsed] = useState(false)
  const [open, setOpen] = useState(false)

  const [conversations, setConversations] = useState<ConversationItem[]>([])
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [convTitle, setConvTitle] = useState('')

  // 加载会话列表
  const loadConversations = useCallback(async () => {
    try {
      const data = await fetchJson<ConversationItem[]>('/api/v1/conversations')
      setConversations(data)
    } catch (e) {
      console.error('加载会话列表失败:', e)
    }
  }, [])

  // 加载会话详情
  const loadConversationDetail = useCallback(async (convId: string) => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchJson<{
        id: string
        title: string
        messages: MessageItem[]
      }>(`/api/v1/conversations/${convId}`)
      setMessages(data.messages)
      setConvTitle(data.title)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  // 新建会话
  const handleCreateConversation = useCallback(async () => {
    try {
      const data = await fetchJson<ConversationItem>('/api/v1/conversations', {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setConversations((prev) => [data, ...prev])
      setSelectedConvId(data.id)
      setMessages([])
      setConvTitle(data.title)
    } catch (e) {
      console.error('创建会话失败:', e)
    }
  }, [])

  // 选择会话
  const handleSelectConversation = useCallback(
    (convId: string) => {
      setSelectedConvId(convId)
      loadConversationDetail(convId)
    },
    [loadConversationDetail]
  )

  // 重命名会话
  const handleRenameConversation = useCallback(
    async (convId: string, title: string) => {
      try {
        await fetchJson(`/api/v1/conversations/${convId}`, {
          method: 'PUT',
          body: JSON.stringify({ title }),
        })
        setConversations((prev) =>
          prev.map((c) => (c.id === convId ? { ...c, title } : c))
        )
        if (convId === selectedConvId) setConvTitle(title)
      } catch (e) {
        console.error('重命名失败:', e)
      }
    },
    [selectedConvId]
  )

  // 删除会话
  const handleDeleteConversation = useCallback(
    async (convId: string) => {
      try {
        await fetchJson(`/api/v1/conversations/${convId}`, { method: 'DELETE' })
        setConversations((prev) => prev.filter((c) => c.id !== convId))
        if (convId === selectedConvId) {
          setSelectedConvId(null)
          setMessages([])
          setConvTitle('')
        }
      } catch (e) {
        console.error('删除会话失败:', e)
      }
    },
    [selectedConvId]
  )

  // 发送消息
  const handleSendMessage = useCallback(
    async (content: string) => {
      let convId = selectedConvId

      // 没有选中会话时，先创建一个
      if (!convId) {
        try {
          const data = await fetchJson<ConversationItem>('/api/v1/conversations', {
            method: 'POST',
            body: JSON.stringify({}),
          })
          convId = data.id
          setConversations((prev) => [data, ...prev])
          setSelectedConvId(data.id)
          setConvTitle(data.title)
        } catch (e) {
          setError('创建会话失败')
          return
        }
      }

      // 添加用户消息
      const userMsg: MessageItem = {
        id: Date.now().toString(),
        role: 'user',
        content,
        metadata: {},
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMsg])
      setLoading(true)
      setError(null)

      try {
        // 调用AI助手
        const response = await fetchJson<{
          reply?: string
          response?: string
          result?: string
        }>('/api/v1/agent/run', {
          method: 'POST',
          body: JSON.stringify({ input: content, conversation_id: convId }),
          timeoutMs: 120000, // AI响应可能较慢，设置120秒超时
        })

        const reply = response.reply || response.response || response.result || '暂无回复'
        const aiMsg: MessageItem = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: reply,
          metadata: {},
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, aiMsg])

        // 如果是第一条消息，更新会话标题
        if (messages.length === 0) {
          const newTitle = content.substring(0, 30) + (content.length > 30 ? '...' : '')
          await fetchJson(`/api/v1/conversations/${convId}`, {
            method: 'PUT',
            body: JSON.stringify({ title: newTitle }),
          })
          setConvTitle(newTitle)
          setConversations((prev) =>
            prev.map((c) => (c.id === convId ? { ...c, title: newTitle } : c))
          )
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
    },
    [selectedConvId, messages.length]
  )

  // 浮窗打开时加载会话列表
  useEffect(() => {
    if (open) {
      loadConversations()
    }
  }, [open, loadConversations])

  return (
    <>
      {/* 收起状态 - 显示一个小按钮在右侧边缘 */}
      {collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          title="展开AI投资助手"
          className="fixed right-0 top-1/2 -translate-y-1/2 z-50 flex h-20 w-10 items-center justify-center rounded-l-xl rounded-r-none border border-r-0 border-zinc-300/60 bg-white/90 backdrop-blur-md text-zinc-800 shadow-lg transition-all hover:bg-white hover:shadow-xl hover:w-12"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
      )}

      {/* 展开状态 */}
      {!collapsed && (
        <>
          {/* 主按钮区域 */}
          <div className="fixed bottom-6 right-6 z-40 flex items-center gap-2">
            <button
              onClick={() => setOpen(true)}
              title="AI 投资助手"
              className="inline-flex select-none items-center gap-2 rounded-full border border-zinc-200 bg-white/92 backdrop-blur-md px-4 py-3 text-sm font-semibold text-zinc-900 shadow-[0_10px_30px_rgba(0,0,0,0.12)] transition-all hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(0,0,0,0.16)]"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-white">
                <Bot className="h-5 w-5" />
              </span>
              <span>AI 投资助手</span>
            </button>
            <button
              onClick={() => setCollapsed(true)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-zinc-200 bg-white/92 backdrop-blur-md text-zinc-600 hover:bg-zinc-100 transition-colors shadow-[0_10px_30px_rgba(0,0,0,0.12)]"
              title="收起"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          {/* 对话浮窗 */}
          {open && (
            <>
              <div className="fixed bottom-24 right-6 z-50 flex w-[480px] overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-[0_18px_48px_rgba(0,0,0,0.22)] transition-all duration-200">
                {/* 左侧会话列表 */}
                <div className="w-36 shrink-0">
                  <ConversationList
                    conversations={conversations}
                    selectedId={selectedConvId}
                    onSelect={handleSelectConversation}
                    onCreate={handleCreateConversation}
                    onRename={handleRenameConversation}
                    onDelete={handleDeleteConversation}
                  />
                </div>

                {/* 右侧对话区域 */}
                <div className="flex flex-1 flex-col">
                  {/* 标题栏 */}
                  <div className="flex h-10 items-center justify-between border-b border-zinc-200 px-3">
                    <div className="truncate text-xs font-semibold text-zinc-900">
                      {convTitle || 'AI 投资助手'}
                    </div>
                    <button
                      onClick={() => setOpen(false)}
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-zinc-500 hover:bg-zinc-100 transition"
                      title="关闭"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>

                  {/* 错误提示 */}
                  {error && (
                    <div className="border-b border-red-100 bg-red-50 px-3 py-1.5 text-[11px] text-red-600">
                      {error}
                    </div>
                  )}

                  {/* 消息列表 */}
                  <MessageList messages={messages} loading={loading} />

                  {/* 输入框 */}
                  <MessageInput onSend={handleSendMessage} disabled={loading} />
                </div>
              </div>

              {/* 点击外部关闭 */}
              <div className="fixed inset-0 z-[45]" onClick={() => setOpen(false)} />
            </>
          )}
        </>
      )}
    </>
  )
}
