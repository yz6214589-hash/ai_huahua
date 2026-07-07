import { useState, useEffect, useCallback } from 'react'
import { Card, CardBody, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Save, RefreshCcw, Settings as SettingsIcon } from 'lucide-react'
import type { SystemSettings } from '@/api/admin'
import { fetchSystemSettings, updateSystemSettings } from '@/api/admin'

const mockSettings: SystemSettings = {
  app_name: 'AI 投资助手',
  log_dir: '/var/log/ai_quant',
  log_max_bytes: 10485760,
  log_backup_count: 7,
  task_timeout: 300,
  llm_timeout: 120,
  report_output_dir: '/data/reports',
  checkpoint_dir: '/data/checkpoints',
}

const FIELDS: { key: keyof SystemSettings; label: string; type: string }[] = [
  { key: 'app_name', label: '应用名称', type: 'text' },
  { key: 'log_dir', label: '日志目录', type: 'text' },
  { key: 'log_max_bytes', label: '日志文件大小(MB)', type: 'number' },
  { key: 'log_backup_count', label: '日志备份数', type: 'number' },
  { key: 'task_timeout', label: '任务超时(秒)', type: 'number' },
  { key: 'llm_timeout', label: 'LLM超时(秒)', type: 'number' },
  { key: 'report_output_dir', label: '研报输出目录', type: 'text' },
  { key: 'checkpoint_dir', label: '检查点目录', type: 'text' },
]

export default function AdminSettings() {
  const [form, setForm] = useState<SystemSettings>({ ...mockSettings })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchSystemSettings()
      setForm(data)
    } catch {
      // 使用 mock 数据
      setForm({ ...mockSettings })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleChange = useCallback((key: keyof SystemSettings, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setMessage(null)
    try {
      await updateSystemSettings(form)
      setMessage({ type: 'success', text: '配置保存成功' })
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : '保存失败' })
    } finally {
      setSaving(false)
    }
  }, [form])

  const handleReset = useCallback(() => {
    setForm({ ...mockSettings })
    setMessage(null)
  }, [])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="基本设置"
          subtitle="配置系统运行参数"
          right={
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={handleReset}>
                <RefreshCcw className="mr-1 h-3.5 w-3.5" />
                重置
              </Button>
              <Button size="sm" onClick={handleSave} disabled={saving}>
                <Save className="mr-1 h-3.5 w-3.5" />
                {saving ? '保存中...' : '保存'}
              </Button>
            </div>
          }
        />
        <CardBody>
          {message && (
            <div
              className={`mb-4 rounded-md border px-4 py-2 text-sm ${
                message.type === 'success'
                  ? 'border-green-200 bg-green-50 text-green-700'
                  : 'border-red-200 bg-red-50 text-red-700'
              }`}
            >
              {message.text}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-10 text-sm text-zinc-400">
              <SettingsIcon className="mr-2 h-5 w-5 animate-spin" />
              加载中...
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">
              {FIELDS.map((field) => (
                <div key={field.key}>
                  <label className="mb-1 block text-sm font-medium text-zinc-700">
                    {field.label}
                  </label>
                  <input
                    type={field.type}
                    value={form[field.key] ?? ''}
                    onChange={(e) => handleChange(field.key, e.target.value)}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
                  />
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
