/**
 * 研报查看器组件
 *
 * 基于 @bytemd/react Viewer 构建，提供：
 * - 左侧固定目录导航（自动提取 Markdown 标题层级）
 * - 右侧 bytemd 纯阅读模式渲染
 * - 目录项与正文联动定位（IntersectionObserver 高亮当前标题）
 * - 代码高亮、数学公式、Mermaid 图表、GFM 表格
 *
 * 实现要点：
 * - bytemd 默认给标题加 id="user-content-..."，TOC 锚点跳转使用该命名规则
 * - 通过 remark 插件为每个标题打上自增序号 id，方便 IntersectionObserver 监听
 * - 容器添加 .report-content className 以应用自定义排版样式
 */
import { Viewer } from '@bytemd/react'
import type { BytemdPlugin } from 'bytemd'
import gfm from '@bytemd/plugin-gfm'
import highlight from '@bytemd/plugin-highlight'
import math from '@bytemd/plugin-math'
import mermaid from '@bytemd/plugin-mermaid'
import { useEffect, useMemo, useRef, useState } from 'react'

// ---- 类型定义 ----

interface HeadingItem {
  /** 标题层级 1-6 */
  level: number
  /** 纯文本标题内容 */
  text: string
  /** 注入到 DOM 中的锚点 ID（与 bytemd 的 user-content- 命名一致） */
  id: string
}

// ---- 工具函数 ----

/**
 * 从 Markdown 文本中解析所有标题（用于构建左侧 TOC）
 *
 * 提取出的 id 与下方 headingIdPlugin 注入的 id 完全一致，
 * 保证点击 TOC 时能找到对应 DOM 节点。
 */
function parseHeadings(md: string): HeadingItem[] {
  const items: HeadingItem[] = []
  const regex = /^(#{1,6})\s+(.+)$/gm
  let match: RegExpExecArray | null
  let idx = 0
  while ((match = regex.exec(md)) !== null) {
    const level = match[1].length
    const text = match[2].trim().replace(/<[^>]*>/g, '')
    const id = `report-heading-${idx}`
    items.push({ level, text, id })
    idx++
  }
  return items
}

/**
 * 通过 remark 插件为每个标题节点注入 id 属性
 *
 * 不能在 Markdown 文本里直接拼 <span id="...">，因为：
 * 1. bytemd 的 sanitize 会过滤空 span
 * 2. 即便不过滤，span 在 HTML 中会作为标题子节点而不是锚点
 *
 * 正确做法是修改 mdast tree，在 heading 节点上加 hProperties.id。
 * bytemd 的 sanitize 默认 schema 已经允许 id 属性。
 *
 * 注意：mdast 的官方 @types/mdast 没有把 hProperties 写入类型，
 * 这里用 any 绕过类型校验，但运行时 bytemd 内部能正确识别。
 */
function headingIdPlugin(): BytemdPlugin {
  let counter = 0
  return {
    remark: (processor: any) =>
      processor.use(() => (tree: any) => {
        counter = 0
        const visit = (node: any) => {
          if (node && node.type === 'heading') {
            const id = `report-heading-${counter}`
            counter++
            node.data = node.data || {}
            node.data.hProperties = { ...(node.data.hProperties || {}), id }
          }
          if (Array.isArray(node?.children)) {
            for (const child of node.children) visit(child)
          }
        }
        visit(tree)
      }),
  }
}

// ---- 插件实例（防止重复创建） ----

const plugins: BytemdPlugin[] = [
  headingIdPlugin(),
  gfm(),
  highlight(),
  math(),
  mermaid(),
]

// ---- 组件属性 ----

interface ReportViewerProps {
  /** Markdown 原文 */
  content: string
  /** 额外的容器类名 */
  className?: string
}

/** 由 bytemd 的 rehype-sanitize clobberPrefix 自动添加的前缀 */
const USER_CONTENT_PREFIX = 'user-content-'

/**
 * 包装 id 为 bytemd 渲染后的实际 DOM ID
 * rehype-sanitize 的默认配置 clobberPrefix: 'user-content-',
 * 会给所有 id 属性加上该前缀以防止 DOM 污染攻击。
 */
function domId(id: string): string {
  return USER_CONTENT_PREFIX + id
}

// ---- 组件 ----

export default function ReportViewer({ content, className = '' }: ReportViewerProps) {
  const [activeId, setActiveId] = useState<string>('')
  const contentRef = useRef<HTMLDivElement>(null)

  const headings = useMemo(() => parseHeadings(content), [content])

  // IntersectionObserver: 高亮当前可视区内的标题
  useEffect(() => {
    const el = contentRef.current
    if (!el || headings.length === 0) return

    const visibleIds = new Set<string>()
    let mostTopId: string | null = null
    let mostTopY = Infinity

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            visibleIds.add(entry.target.id)
            const y = entry.boundingClientRect.top
            if (y < mostTopY) {
              mostTopY = y
              mostTopId = entry.target.id
            }
          } else {
            visibleIds.delete(entry.target.id)
          }
        }
        // 优先用最靠近顶部的可见标题，没有则用第一个
        if (mostTopId && visibleIds.has(mostTopId)) {
          setActiveId(mostTopId)
        } else if (visibleIds.size > 0) {
          setActiveId(visibleIds.values().next().value)
        }
      },
      { rootMargin: '-80px 0px -65% 0px', threshold: 0 }
    )

    // 找到所有 bytemd 渲染后带 id 的 heading 元素
    const targets = el.querySelectorAll(
      'h1, h2, h3, h4, h5, h6',
    ) as NodeListOf<HTMLElement>
    const observed: HTMLElement[] = []
    for (const t of Array.from(targets)) {
      if (t.id) {
        observer.observe(t)
        observed.push(t)
      }
    }

    return () => {
      for (const t of observed) observer.unobserve(t)
      observer.disconnect()
    }
  }, [content, headings.length])

  // 点击 TOC 项滚动到对应标题
  const scrollToHeading = (id: string) => {
    const target = document.getElementById(domId(id))
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveId(domId(id))
    }
  }

  /**
   * 判断 TOC 项是否高亮
   * activeId 是 bytemd 生成的完整 ID（如 user-content-report-heading-2），
   * 而 headings[].id 是我们的内部 ID（如 report-heading-2）。
   */
  const isActive = (internalId: string) => {
    return activeId === domId(internalId) || activeId === internalId
  }

  // ---- 渲染 ----

  return (
    <div className={`flex h-full overflow-hidden ${className}`}>
      {/* 左侧 TOC 目录导航 */}
      {headings.length > 0 && (
        <aside className="w-56 flex-shrink-0 overflow-y-auto border-r border-zinc-200 bg-zinc-50 p-3">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">
            目录
          </div>
          <nav className="space-y-0.5">
            {headings.map((h) => (
              <button
                key={h.id}
                type="button"
                onClick={() => scrollToHeading(h.id)}
                className={`block w-full truncate rounded px-2 py-1 text-left text-xs leading-relaxed transition-colors ${
                  isActive(h.id)
                    ? 'bg-zinc-200 font-medium text-zinc-900'
                    : 'text-zinc-600 hover:bg-zinc-100 hover:text-zinc-800'
                }`}
                style={{ paddingLeft: `${(h.level - 1) * 14 + 8}px` }}
                title={h.text}
              >
                {h.text}
              </button>
            ))}
          </nav>
        </aside>
      )}

      {/* 右侧研报内容 */}
      <main
        ref={contentRef}
        className="report-content flex-1 overflow-y-auto bg-white"
      >
        <div className="mx-auto max-w-3xl px-8 py-6">
          <Viewer
            value={content}
            plugins={plugins}
            // rehype-sanitize 默认只允许 className，需要显式放行 id 属性
            sanitize={(schema) => {
              if (!schema.attributes) schema.attributes = {}
              if (!schema.attributes['*']) schema.attributes['*'] = []
              if (!schema.attributes['*'].includes('id')) {
                schema.attributes['*'].push('id')
              }
              return schema
            }}
          />
        </div>
      </main>
    </div>
  )
}
