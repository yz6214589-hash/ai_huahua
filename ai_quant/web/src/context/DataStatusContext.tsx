/**
 * 全局数据状态上下文
 * 在应用启动时预加载数据状态，供各个页面共享使用
 */

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { fetchJson } from '@/api/client'

export interface DataStatus {
  stock_daily: {
    latest_date: string | null
    stock_count: number
    data_count: number
  } | null
  stock_financial: {
    latest_date: string | null
    stock_count: number
    data_count: number
  } | null
  timestamp: string
}

interface DataStatusContextType {
  dataStatus: DataStatus | null
  loading: boolean
  refresh: () => Promise<void>
}

const DataStatusContext = createContext<DataStatusContextType | undefined>(undefined)

export function DataStatusProvider({ children }: { children: ReactNode }) {
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchDataStatus = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchJson<DataStatus>('/api/v1/data/status')
      setDataStatus(data)
    } catch (error) {
      console.error('获取数据状态失败:', error)
      setDataStatus(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // 在Provider挂载时就开始预加载数据状态
  useEffect(() => {
    fetchDataStatus()
  }, [fetchDataStatus])

  return (
    <DataStatusContext.Provider value={{ dataStatus, loading, refresh: fetchDataStatus }}>
      {children}
    </DataStatusContext.Provider>
  )
}

export function useDataStatus() {
  const context = useContext(DataStatusContext)
  if (context === undefined) {
    throw new Error('useDataStatus must be used within a DataStatusProvider')
  }
  return context
}
