import { useCallback, useRef, useState } from 'react'
import { streamAtlas } from '../api/atlas'
import { toMessage } from '../api/client'
import type { AtlasEdge, AtlasNode, AtlasResponse } from '../types/atlas'
import type { ProgressEvent, StageEvent } from '../types/stream'

export type GenerationStatus = 'idle' | 'running' | 'done' | 'failed'

export interface AtlasStreamState {
    status: GenerationStatus
    stage: StageEvent | null
    progress: ProgressEvent | null
    /** 已到达的节点，用于边生成边画图 */
    nodes: AtlasNode[]
    edges: AtlasEdge[]
    /** 完整结果，仅在收到 result 事件后才有值；用于渲染概述与跨领域思路 */
    atlas: AtlasResponse | null
    error: string | null
}

const IDLE: AtlasStreamState = {
    status: 'idle',
    stage: null,
    progress: null,
    nodes: [],
    edges: [],
    atlas: null,
    error: null,
}

/** 判重用的边标识。同一对节点之间的不同关系是合法的，所以 relation 要计入 */
function edgeKey(edge: AtlasEdge): string {
    return `${edge.source}\u0000${edge.target}\u0000${edge.relation}`
}

/**
 * 把 SSE 事件流变成 React state。
 *
 * 组件因此完全不必接触原始帧、ReadableStream 或状态码语义。
 */
export function useAtlasStream() {
    const [state, setState] = useState<AtlasStreamState>(IDLE)
    const abortRef = useRef<AbortController | null>(null)

    const generate = useCallback(async (query: string, provider: string) => {
        // 取消上一条仍在进行的流，避免两次生成并发写同一份 state
        abortRef.current?.abort()
        const controller = new AbortController()
        abortRef.current = controller

        setState({ ...IDLE, status: 'running' })

        try {
            await streamAtlas(query, provider, {
                signal: controller.signal,
                onEvent: (event) => {
                    setState((prev) => {
                        switch (event.type) {
                            case 'stage':
                                return { ...prev, stage: event }
                            case 'progress':
                                return { ...prev, progress: event }

                            case 'node':
                                // 重复 id 会让 React key 冲突、dagre 出现重复顶点。
                                // 正常不会发生，但代价只是一次比较，值得挡住。
                                if (
                                    prev.nodes.some(
                                        (node) => node.id === event.node.id,
                                    )
                                ) {
                                    return prev
                                }
                                return {
                                    ...prev,
                                    nodes: [...prev.nodes, event.node],
                                }

                            case 'edge': {
                                const key = edgeKey(event.edge)
                                if (
                                    prev.edges.some(
                                        (edge) => edgeKey(edge) === key,
                                    )
                                ) {
                                    return prev
                                }
                                return {
                                    ...prev,
                                    edges: [...prev.edges, event.edge],
                                }
                            }

                            case 'result':
                                // 以最终结果为准做一次校准，而不是直接丢弃增量。
                                // 两者本应一致（后端对增量与整体走的是同一套校验），
                                // 但把权威版本落到同一份 state 里，图与概述就不会
                                // 出现源自两个数据源的不一致。
                                return {
                                    ...prev,
                                    status: 'done',
                                    atlas: event.atlas,
                                    nodes: event.atlas.nodes,
                                    edges: event.atlas.edges,
                                }

                            case 'error':
                                return {
                                    ...prev,
                                    status: 'failed',
                                    error: event.detail,
                                }

                            default:
                                // 类型上是穷尽的，但运行时不是：后端将来新增的
                                // 事件类型会落到这里。必须原样返回，否则 updater
                                // 返回 undefined 会把整个 state 覆盖掉。
                                return prev
                        }
                    })
                },
            })

            // 流已关闭却没收到任何终止事件 —— 连接被中途掐断（反代超时、进程退出）。
            // 这是 SSE 最容易漏掉的一种失败：状态码是 200，但什么也没说。
            setState((prev) =>
                prev.status === 'running'
                    ? {
                          ...prev,
                          status: 'failed',
                          error: '连接被中断，没有收到完整图谱，请重试',
                      }
                    : prev,
            )
        } catch (error) {
            if (controller.signal.aborted) return // 主动取消不算失败
            setState((prev) => ({
                ...prev,
                status: 'failed',
                error: toMessage(error),
            }))
        }
    }, [])

    const reset = useCallback(() => {
        abortRef.current?.abort()
        setState(IDLE)
    }, [])

    return { ...state, generate, reset }
}
