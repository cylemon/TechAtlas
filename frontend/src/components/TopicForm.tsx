import { useState } from 'react'

interface TopicFormProps {
    providers: string[]
    busy: boolean
    onSubmit: (query: string, provider: string) => void
}

export function TopicForm({ providers, busy, onSubmit }: TopicFormProps) {
    const [query, setQuery] = useState('')
    const [selectedProvider, setSelectedProvider] = useState('')

    // 派生而非用 effect 同步：用户没显式选过就回落到第一个可用厂商。
    // provider 列表是异步到达的，用 effect + setState 补默认值会造成级联渲染。
    const provider = selectedProvider || providers[0] || ''

    const trimmed = query.trim()
    // 与后端 AtlasGenerateRequest 的约束保持一致：query 至少 2 个字符
    const canSubmit = !busy && provider !== '' && trimmed.length >= 2

    return (
        <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
                event.preventDefault()
                if (canSubmit) onSubmit(trimmed, provider)
            }}
        >
            <input
                type="text"
                value={query}
                maxLength={100}
                disabled={busy}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="输入技术课题，例如：AI Agent 技术全景"
                className="min-w-0 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm
                           text-slate-900 placeholder:text-slate-400
                           focus:border-slate-500 focus:outline-none
                           disabled:bg-slate-50 disabled:text-slate-400"
            />

            <select
                value={provider}
                disabled={busy || providers.length === 0}
                onChange={(event) => setSelectedProvider(event.target.value)}
                aria-label="LLM 提供商"
                className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700
                           focus:border-slate-500 focus:outline-none disabled:bg-slate-50"
            >
                {providers.length === 0 && <option value="">加载中…</option>}
                {providers.map((name) => (
                    <option key={name} value={name}>
                        {name}
                    </option>
                ))}
            </select>

            <button
                type="submit"
                disabled={!canSubmit}
                className="rounded-md bg-slate-900 px-5 py-2 text-sm font-medium text-white
                           hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
                {busy ? '生成中…' : '生成图谱'}
            </button>
        </form>
    )
}
