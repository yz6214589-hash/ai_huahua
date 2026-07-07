import { useState, useEffect, useCallback, useRef } from 'react';
import { Plus, Search, Trash2, Pencil, X, Send, Bot, User, MoreVertical, MessageSquare, ChevronLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchJson, postJson } from '@/api/client';
interface MessageItem {
 id: string;
 role: string;
 content: string;
 metadata: Record<string, any>;
 created_at: string;
}
interface ConversationItem {
 id: string;
 title: string;
 created_at: string;
 updated_at: string;
 message_count: number;
}
function formatDate(dateStr: string): string {
 const date = new Date(dateStr);
 const now = new Date();
 const diff = now.getTime() - date.getTime();
 const minutes = Math.floor(diff / 60000);
 const hours = Math.floor(diff / 3600000);
 const days = Math.floor(diff / 86400000);
 if (minutes < 1)
 return '刚刚';
 if (minutes < 60)
 return `${minutes}分钟前`;
 if (hours < 24)
 return `${hours}小时前`;
 if (days < 7)
 return `${days}天前`;
 return date.toLocaleDateString('zh-CN');
}
function formatFullDate(dateStr: string): string {
 const date = new Date(dateStr);
 return date.toLocaleString('zh-CN', {
 month: '2-digit',
 day: '2-digit',
 hour: '2-digit',
 minute: '2-digit',
 });
}
// 会话列表组件
function ConversationList({
 conversations,
 selectedId,
 onSelect,
 onCreate,
 onRename,
 onDelete,
}: {
 conversations: ConversationItem[];
 selectedId: string | null;
 onSelect: (id: string) => void;
 onCreate: () => void;
 onRename: (id: string, title: string) => void;
 onDelete: (id: string) => void;
}) {
 const [search, setSearch] = useState('');
 const [contextMenu, setContextMenu] = useState<{
 x: number;
 y: number;
 convId: string;
 title: string;
 } | null>(null);
 const [editingId, setEditingId] = useState<string | null>(null);
 const [editingTitle, setEditingTitle] = useState('');
 const filteredConvs = conversations.filter((conv) => conv.title.toLowerCase().includes(search.toLowerCase()));
 const handleContextMenu = (e: React.MouseEvent, conv: ConversationItem) => {
 e.preventDefault();
 setContextMenu({
 x: e.clientX,
 y: e.clientY,
 convId: conv.id,
 title: conv.title,
 });
 };
 const handleCloseContextMenu = () => {
 setContextMenu(null);
 };
 const handleStartRename = (convId: string, title: string) => {
 setEditingId(convId);
 setEditingTitle(title);
 setContextMenu(null);
 };
 const handleSaveRename = () => {
 if (editingId && editingTitle.trim()) {
 onRename(editingId, editingTitle.trim());
 }
 setEditingId(null);
 setEditingTitle('');
 };
 const handleCancelRename = () => {
 setEditingId(null);
 setEditingTitle('');
 };
 return (<div className="flex h-full flex-col border-r border-zinc-200 bg-zinc-50">
 {/* 头部 */}
 <div className="border-b border-zinc-200 p-3">
 <div className="mb-3 flex items-center justify-between">
 <h2 className="text-base font-semibold text-zinc-900">AI 投资助手</h2>
 <button onClick={onCreate} className="flex h-8 w-8 items-center justify-center rounded-lg bg-zinc-900 text-white transition hover:bg-zinc-800" title="新建会话">
 <Plus className="h-4 w-4"/>
 </button>
 </div>
 {/* 搜索框 */}
 <div className="relative">
 <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"/>
 <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="搜索会话..." className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-8 pr-3 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-400 focus:outline-none"/>
 </div>
 </div>

 {/* 会话列表 */}
 <div className="flex-1 overflow-y-auto">
 {filteredConvs.length === 0 ? (<div className="flex flex-col items-center justify-center py-12 text-zinc-400">
 <MessageSquare className="mb-2 h-8 w-8"/>
 <span className="text-sm">暂无会话</span>
 </div>) : (filteredConvs.map((conv) => (<div key={conv.id} className={cn('group relative flex items-center gap-3 px-3 py-2.5 cursor-pointer transition', selectedId === conv.id
 ? 'bg-white border-l-2 border-l-blue-500'
 : 'hover:bg-white')} onClick={() => onSelect(conv.id)} onContextMenu={(e) => handleContextMenu(e, conv)}>
 {/* 编辑模式 */}
 {editingId === conv.id ? (<div className="flex flex-1 items-center gap-2">
 <input type="text" value={editingTitle} onChange={(e) => setEditingTitle(e.target.value)} onKeyDown={(e) => {
 if (e.key === 'Enter')
 handleSaveRename();
 if (e.key === 'Escape')
 handleCancelRename();
 }} autoFocus className="flex-1 rounded border border-blue-400 px-2 py-1 text-sm font-medium text-zinc-900 focus:outline-none focus:ring-2 focus:ring-blue-200"/>
 <button onClick={(e) => { e.stopPropagation(); handleSaveRename(); }} className="rounded p-1 text-emerald-600 hover:bg-emerald-50" title="保存">
 <Pencil className="h-3.5 w-3.5"/>
 </button>
 <button onClick={(e) => { e.stopPropagation(); handleCancelRename(); }} className="rounded p-1 text-zinc-400 hover:bg-zinc-100" title="取消">
 <X className="h-3.5 w-3.5"/>
 </button>
 </div>) : (<>
 <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-zinc-100 text-zinc-600">
 <Bot className="h-4 w-4"/>
 </div>
 <div className="flex flex-1 min-w-0 items-center justify-between">
 <div className="min-w-0">
 <div className="truncate text-sm font-medium text-zinc-900">
 {conv.title || '无标题'}
 </div>
 <div className="truncate text-xs text-zinc-400">
 {conv.message_count} 条消息 · {formatDate(conv.updated_at)}
 </div>
 </div>
 {/* 更多按钮 */}
 <button onClick={(e) => {
 e.stopPropagation();
 handleContextMenu(e, conv);
 }} className="opacity-0 transition opacity group-hover:opacity-100" title="更多操作">
 <MoreVertical className="h-4 w-4 text-zinc-400"/>
 </button>
 </div>
 </>)}
 </div>)))}
 </div>

 {/* 右键菜单 */}
 {contextMenu && (<>
 <div className="fixed inset-0 z-50" onClick={handleCloseContextMenu}/>
 <div className="fixed z-50 w-36 rounded-lg border border-zinc-200 bg-white shadow-lg" style={{ left: contextMenu.x, top: contextMenu.y }}>
 <button onClick={() => {
 handleStartRename(contextMenu.convId, contextMenu.title);
 handleCloseContextMenu();
 }} className="flex w-full items-center gap-2 px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50" title="重命名">
 <Pencil className="h-4 w-4"/>
 重命名
 </button>
 <button onClick={() => {
 onDelete(contextMenu.convId);
 handleCloseContextMenu();
 }} className="flex w-full items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50" title="删除会话">
 <Trash2 className="h-4 w-4"/>
 删除会话
 </button>
 </div>
 </>)}
 </div>);
}
// 消息输入组件
function MessageInput({ onSend, disabled }: {
 onSend: (content: string) => void;
 disabled: boolean;
}) {
 const [input, setInput] = useState('');
 const handleSend = () => {
 const content = input.trim();
 if (content && !disabled) {
 onSend(content);
 setInput('');
 }
 };
 const handleKeyDown = (e: React.KeyboardEvent) => {
 if (e.key === 'Enter' && !e.shiftKey) {
 e.preventDefault();
 handleSend();
 }
 };
 return (<div className="border-t border-zinc-200 p-4">
 <div className="flex items-end gap-3">
 <div className="flex-1 rounded-2xl border border-zinc-200 bg-white px-4 py-3 shadow-sm transition focus-within:border-zinc-400 focus-within:ring-2 focus-within:ring-zinc-100">
 <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="输入您的问题..." rows={2} disabled={disabled} className="w-full resize-none bg-transparent text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none" style={{ minHeight: '44px' }}/>
 </div>
 <button onClick={handleSend} disabled={!input.trim() || disabled} className={cn('flex h-12 w-12 items-center justify-center rounded-full transition', disabled || !input.trim()
 ? 'bg-zinc-100 text-zinc-400 cursor-not-allowed'
 : 'bg-zinc-900 text-white hover:bg-zinc-800')} title="发送">
 <Send className="h-5 w-5"/>
 </button>
 </div>
 </div>);
}
// 消息列表组件
function MessageList({ messages, loading }: {
 messages: MessageItem[];
 loading: boolean;
}) {
 const scrollRef = useRef<HTMLDivElement>(null);
 useEffect(() => {
 if (scrollRef.current) {
 scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
 }
 }, [messages]);
 return (<div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-4">
 {messages.length === 0 && !loading ? (<div className="flex flex-col items-center justify-center py-16 text-zinc-400">
 <Bot className="mb-4 h-12 w-12 text-zinc-300"/>
 <h3 className="mb-2 text-lg font-semibold text-zinc-900">欢迎使用 AI 投资助手</h3>
 <p className="text-sm">请从左侧选择一个对话，或新建一个对话开始交流</p>
 <div className="mt-6 space-y-2 text-left text-sm">
 <p className="font-medium text-zinc-700">推荐问题：</p>
 <ul className="space-y-1 list-disc pl-4">
 <li>请生成今日晨会简报</li>
 <li>帮我分析贵州茅台的投资价值</li>
 <li>最近有哪些热门板块？</li>
 <li>推荐几只低估值蓝筹股</li>
 </ul>
 </div>
 </div>) : (<div className="space-y-4">
 {messages.map((msg) => {
 const isUser = msg.role === 'user';
 return (<div key={msg.id} className={cn('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
 <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-full', isUser
 ? 'bg-blue-100 text-blue-600'
 : 'bg-emerald-100 text-emerald-600')}>
 {isUser ? <User className="h-4 w-4"/> : <Bot className="h-4 w-4"/>}
 </div>
 <div className={cn('max-w-[75%] rounded-lg px-4 py-3 text-sm', isUser
 ? 'bg-blue-50 text-zinc-800 rounded-br-sm'
 : 'bg-zinc-50 text-zinc-800 rounded-bl-sm')}>
 <div className="mb-1 flex items-center gap-2">
 <span className="text-xs font-medium text-zinc-500">
 {isUser ? '你' : 'AI 助手'}
 </span>
 <span className="text-xs text-zinc-400">
 {formatFullDate(msg.created_at)}
 </span>
 </div>
 <div className="whitespace-pre-wrap break-words leading-relaxed">
 {msg.content}
 </div>
 </div>
 </div>);
 })}
 {loading && (<div className="flex justify-center py-4">
 <div className="flex h-5 w-5 items-center gap-1">
 <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-900"/>
 <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-900" style={{ animationDelay: '0.1s' }}/>
 <div className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-900" style={{ animationDelay: '0.2s' }}/>
 </div>
 </div>)}
 </div>)}
 </div>);
}
// 主页面组件
export default function AgentChat() {
 const [conversations, setConversations] = useState<ConversationItem[]>([]);
 const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
 const [messages, setMessages] = useState<MessageItem[]>([]);
 const [loading, setLoading] = useState(false);
 const [error, setError] = useState<string | null>(null);
 const [convTitle, setConvTitle] = useState('');
 // 加载会话列表
 const loadConversations = useCallback(async () => {
 try {
 const data = await fetchJson<ConversationItem[]>('/api/v1/conversations');
 setConversations(data);
 }
 catch (e) {
 console.error('Failed to load conversations:', e);
 }
 }, []);
 // 加载会话详情
 const loadConversationDetail = useCallback(async (convId: string) => {
 setLoading(true);
 setError(null);
 try {
 const data = await fetchJson<{
 id: string;
 title: string;
 messages: MessageItem[];
 }>(`/api/v1/conversations/${convId}`);
 setMessages(data.messages);
 setConvTitle(data.title);
 }
 catch (e) {
 setError(e instanceof Error ? e.message : String(e));
 }
 finally {
 setLoading(false);
 }
 }, []);
 // 新建会话
 const handleCreateConversation = useCallback(async () => {
 try {
 const data = await postJson<ConversationItem>('/api/v1/conversations', {});
 setConversations((prev) => [data as ConversationItem, ...prev]);
 setSelectedConvId(data.id);
 setMessages([]);
 setConvTitle(data.title);
 }
 catch (e) {
 console.error('Failed to create conversation:', e);
 }
 }, []);
 // 选择会话
 const handleSelectConversation = useCallback((convId: string) => {
 setSelectedConvId(convId);
 loadConversationDetail(convId);
 }, [loadConversationDetail]);
 // 重命名会话
 const handleRenameConversation = useCallback(async (convId: string, title: string) => {
 try {
 await fetchJson(`/api/v1/conversations/${convId}`, {
 method: 'PUT',
 body: JSON.stringify({ title }),
 });
 setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, title } : c)));
 if (convId === selectedConvId) {
 setConvTitle(title);
 }
 }
 catch (e) {
 console.error('Failed to rename conversation:', e);
 }
 }, [selectedConvId]);
 // 删除会话
 const handleDeleteConversation = useCallback(async (convId: string) => {
 try {
 await fetchJson(`/api/v1/conversations/${convId}`, { method: 'DELETE' });
 setConversations((prev) => prev.filter((c) => c.id !== convId));
 if (convId === selectedConvId) {
 setSelectedConvId(null);
 setMessages([]);
 setConvTitle('');
 }
 }
 catch (e) {
 console.error('Failed to delete conversation:', e);
 }
 }, [selectedConvId]);
 // 发送消息
 const handleSendMessage = useCallback(async (content: string) => {
 if (!selectedConvId) {
 // 如果没有选中会话，先创建一个
 try {
 const data = await postJson<ConversationItem>('/api/v1/conversations', {});
 setConversations((prev) => [data as ConversationItem, ...prev]);
 setSelectedConvId(data.id);
 setConvTitle(data.title);
 // 添加用户消息
 const userMsg: MessageItem = {
 id: Date.now().toString(),
 role: 'user',
 content,
 metadata: {},
 created_at: new Date().toISOString(),
 };
 setMessages([userMsg]);
 // 调用AI助手
 setLoading(true);
 const response = await fetchJson<{
 reply: string;
 }>('/api/v1/agent/run', {
 method: 'POST',
 body: JSON.stringify({ input: content, conversation_id: data.id }),
 });
 const aiMsg: MessageItem = {
 id: (Date.now() + 1).toString(),
 role: 'assistant',
 content: response.reply,
 metadata: {},
 created_at: new Date().toISOString(),
 };
 setMessages((prev) => [...prev, aiMsg]);
 // 更新会话标题
 const newTitle = content.substring(0, 50) + (content.length > 50 ? '...' : '');
 await fetchJson(`/api/v1/conversations/${data.id}`, {
 method: 'PUT',
 body: JSON.stringify({ title: newTitle }),
 });
 setConvTitle(newTitle);
 setConversations((prev) => prev.map((c) => (c.id === data.id ? { ...c, title: newTitle } : c)));
 setLoading(false);
 }
 catch (e) {
 setError(e instanceof Error ? e.message : String(e));
 setLoading(false);
 }
 }
 else {
 // 添加用户消息
 const userMsg: MessageItem = {
 id: Date.now().toString(),
 role: 'user',
 content,
 metadata: {},
 created_at: new Date().toISOString(),
 };
 setMessages((prev) => [...prev, userMsg]);
 // 调用AI助手
 setLoading(true);
 try {
 const response = await fetchJson<{
 reply: string;
 }>('/api/v1/agent/run', {
 method: 'POST',
 body: JSON.stringify({ input: content, conversation_id: selectedConvId }),
 });
 const aiMsg: MessageItem = {
 id: (Date.now() + 1).toString(),
 role: 'assistant',
 content: response.reply,
 metadata: {},
 created_at: new Date().toISOString(),
 };
 setMessages((prev) => [...prev, aiMsg]);
 }
 catch (e) {
 setError(e instanceof Error ? e.message : String(e));
 }
 finally {
 setLoading(false);
 }
 }
 }, [selectedConvId]);
 useEffect(() => {
 loadConversations();
 }, [loadConversations]);
 return (<div className="flex h-screen flex-col bg-white">
 {/* 顶部导航栏 */}
 <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
 <div className="flex items-center gap-3">
 <div className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-white">
 <Bot className="h-5 w-5"/>
 </div>
 <div>
 <h1 className="text-base font-semibold text-zinc-900">AI 投资助手</h1>
 <p className="text-xs text-zinc-500">智能投资分析与研究辅助</p>
 </div>
 </div>
 </header>

 {/* 主体内容 */}
 <div className="flex flex-1 overflow-hidden">
 {/* 左侧会话列表 */}
 <div className="w-72 flex-shrink-0">
 <ConversationList conversations={conversations} selectedId={selectedConvId} onSelect={handleSelectConversation} onCreate={handleCreateConversation} onRename={handleRenameConversation} onDelete={handleDeleteConversation}/>
 </div>

 {/* 右侧对话区域 */}
 <div className="flex flex-1 flex-col">
 {/* 会话标题栏 */}
 {selectedConvId && (<div className="flex items-center justify-between border-b border-zinc-200 px-6 py-3">
 <h2 className="truncate text-base font-semibold text-zinc-900">
 {convTitle || '会话'}
 </h2>
 <button onClick={() => {
 setSelectedConvId(null);
 setMessages([]);
 setConvTitle('');
 }} className="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-600" title="返回会话列表">
 <ChevronLeft className="h-5 w-5"/>
 </button>
 </div>)}

 {/* 消息列表 */}
 <MessageList messages={messages} loading={loading}/>

 {/* 错误提示 */}
 {error && (<div className="border-t border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
 {error}
 </div>)}

 {/* 消息输入框 */}
 {selectedConvId && (<MessageInput onSend={handleSendMessage} disabled={loading}/>)}
 </div>
 </div>
 </div>);
}