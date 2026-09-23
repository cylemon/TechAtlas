import { useEffect, useState } from 'react'
import { fetchProviders } from './api/atlas'
import { toMessage } from './api/client'
import { AtlasGraph } from './components/AtlasGraph'
import { GenerationProgress } from './components/GenerationProgress'
import { TopicForm } from './components/TopicForm'
import { useAtlasStream } from './hooks/useAtlasStream'
import type { AtlasResponse } from './types/atlas'

function EmptyState() {
    return (
        <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <p className="text-sm text-slate-500">还没有图谱</p>
            <p className="max-w-xs text-xs text-slate-400">
                在上方输入一个技术课题，例如「AI Agent 技术全景」或「向量数据库」
            </p>
        </div>
    )
}

function ErrorState({ message }: { message: string | null }) {
    return (
        <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <p className="text-sm font-medium text-red-600">生成失败</p>
            <p className="max-w-md text-xs text-slate-500">{message}</p>
        </div>
    )
}

function ResultSummary({ atlas }: { atlas: AtlasResponse }) {
    const ideas = atlas.cross_domain_ideas ?? []

    return (
        <div className="border-b border-slate-200 bg-white px-6 py-3">
            <h2 className="text-sm font-semibold text-slate-900">{atlas.topic}</h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-600">
                {atlas.summary}
            </p>

            {ideas.length > 0 && (
                <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">
                        跨领域融合思路（{ideas.length}）
                    </summary>
                    <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs leading-relaxed text-slate-600">
                        {ideas.map((idea) => (
                            <li key={idea}>{idea}</li>
                        ))}
                    </ul>
                </details>
            )}
        </div>
    )
}

export default function App() {
    const [providers, setProviders] = useState<string[]>([])
    const [providerError, setProviderError] = useState<string | null>(null)
    const { status, stage, progress, nodes, edges, atlas, error, generate } =
        useAtlasStream()

    useEffect(() => {
        fetchProviders()
            .then(setProviders)
            .catch((cause) => setProviderError(toMessage(cause)))
    }, [])

    return (
        <div className="flex h-screen flex-col bg-slate-50">
            <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
                <h1 className="text-base font-semibold text-slate-900">TechAtlas</h1>
                <p className="mt-0.5 text-xs text-slate-500">
                    输入一个技术课题，得到它的结构图谱
                </p>

                <div className="mt-3">
                    <TopicForm
                        providers={providers}
                        busy={status === 'running'}
                        onSubmit={generate}
                    />
                </div>

                {providerError && (
                    <p className="mt-2 text-xs text-red-600">
                        无法获取可用厂商：{providerError}
                    </p>
                )}
            </header>

            {status === 'done' && atlas && <ResultSummary atlas={atlas} />}

            <main className="relative min-h-0 flex-1">
                {status === 'idle' && <EmptyState />}
                {status === 'failed' && <ErrorState message={error} />}

                {/* 生成中且还没有节点：图上无物可画，先占满整屏说清楚在等什么 */}
                {status === 'running' && nodes.length === 0 && (
                    <GenerationProgress stage={stage} progress={progress} />
                )}

                {(nodes.length > 0 || (status === 'done' && atlas)) && (
                    <>
                        <AtlasGraph nodes={nodes} edges={edges} />

                        {/* 节点一到达就换成浮在图上的进度条，把画面让给图谱本身。
                            放底部居中：上方留给图例，左右下角分别被 Controls 与 MiniMap 占着 */}
                        {status === 'running' && (
                            <div className="pointer-events-none absolute inset-x-0 bottom-4 z-10 flex justify-center">
                                <GenerationProgress compact stage={stage} progress={progress} />
                            </div>
                        )}
                    </>
                )}
            </main>
        </div>
    )
}
