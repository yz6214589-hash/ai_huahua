import { cn } from '@/lib/utils'
import { CheckCircle, XCircle } from 'lucide-react'
import React, { useEffect, useState } from 'react'

export type ToastType = 'success' | 'error'

export interface ToastMessage {
  id: number
  type: ToastType
  message: string
}

let _setToasts: React.Dispatch<React.SetStateAction<ToastMessage[]>> | null = null
let _nextId = 0
let _timers: Map<number, NodeJS.Timeout> = new Map()

export function toast(type: ToastType, message: string) {
  if (!_setToasts) return
  const id = ++_nextId
  _setToasts((prev) => [...prev, { id, type, message }])
  const timerId = setTimeout(() => {
    _setToasts?.((prev) => prev.filter((m) => m.id !== id))
    _timers.delete(id)
  }, 3000)
  _timers.set(id, timerId)
}

export function ToastContainer() {
  const [msgs, setMsgs] = useState<ToastMessage[]>([])
  useEffect(() => {
    _setToasts = setMsgs
    return () => {
      // 清理所有未执行的定时器
      _timers.forEach((timerId) => clearTimeout(timerId))
      _timers.clear()
      _setToasts = null
    }
  }, [])
  return (
    <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2">
      {msgs.map((m) => (
        <div
          key={m.id}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-4 py-3 shadow-md text-sm animate-in slide-in-from-top',
            m.type === 'success' ? 'border-green-200 bg-green-50 text-green-800' : 'border-red-200 bg-red-50 text-red-800'
          )}
        >
          {m.type === 'success' ? <CheckCircle className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
          {m.message}
        </div>
      ))}
    </div>
  )
}
