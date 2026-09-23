import { useEffect, useState } from 'react'
import { SECTION_LABEL, type ProgressEvent, type StageEvent } from '../types/stream'

interface GenerationProgressProps {
    stage: StageEvent | null
    progress: ProgressEvent | null
    /** 图上已经有节点时改用紧凑样式：此时图本身就是进度条，不该被它挡住 */
    compact?: boolean
}

function formatElapsed(ms: number): string {
    return `${(ms / 1000).toFixed(1)}s`
}

export function GenerationProgress({ stage, progress, compact }: GenerationProgressProps) {
    // 后端刻意不报百分比（总量事先不可知），所以这里只显示一句阶段说明 +
    // 两个客观计数。秒表本地走字，避免进度看起来"卡住了"。
    const [elapsed, setElapsed] = useState(0)

    useEffect(() => {
        const started = Date.now()
        const timer = setInterval(() => setElapsed(Date.now() - started), 100)
        return () => clearInterval(timer)
    }, [])

    const section = progress?.section ? SECTION_LABEL[progress.section] : null
    const time = formatElapsed(progress?.elapsed_ms ?? elapsed)

    if (compact) {
        return (
            <div className="flex items-center gap-2.5 rounded-full border border-slate-200 bg-white/95 px-4 py-1.5 shadow-sm backdrop-blur">
                <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700" />
                <span className="text-xs font-medium text-slate-700">
                    {stage?.label ?? '正在连接…'}
                </span>
                <span className="text-xs tabular-nums text-slate-400">
                    {time}
                    {section && ` · 正在生成${section}`}
                </span>
            </div>
        )
    }

    return (
        <div className="flex flex-col items-center gap-4 py-20">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700" />

            <div className="text-center">
                <p className="text-sm font-medium text-slate-700">
                    {stage?.label ?? '正在连接…'}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                    {time}
                    {section && ` · 正在生成${section}`}
                    {progress != null && progress.received_chars > 0 && (
                        <> · 已接收 {progress.received_chars} 字符</>
                    )}
                </p>
            </div>
        </div>
    )
}
