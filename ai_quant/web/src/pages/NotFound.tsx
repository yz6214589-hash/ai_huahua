import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl rounded-xl border border-zinc-200 bg-white p-6">
      <div className="text-sm font-semibold text-zinc-900">页面不存在</div>
      <div className="mt-2 text-sm text-zinc-600">请返回总览或从左侧导航进入。</div>
      <div className="mt-4">
        <Link to="/" className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white">
          回到总览
        </Link>
      </div>
    </div>
  )
}

