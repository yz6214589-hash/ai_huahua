/// <reference types="react" />
/**
 * 研报查看器 Mock 组件
 * 用于 jsdom 测试环境（bytemd 基于 Svelte，在 Node.js 中无法渲染）
 * 以纯文本 div 替代真实的 bytemd Viewer + TOC 布局
 */
import type { FC } from 'react'
interface ReportViewerProps {
  content: string
  className?: string
}
const MockReportViewer: FC<ReportViewerProps> = ({ content }) => {
  const { createElement } = require('react')
  return createElement('div', { 'data-testid': 'mock-viewer' }, content)
}
export default MockReportViewer
