import type { AtlasStreamEvent } from '../types/stream'
import { readErrorDetail } from './client'

/** 拉取已注册的 LLM 提供商，用于渲染选择菜单 */
export async function fetchProviders(): Promise<string[]> {
    const response = await fetch('/api/providers')
    if (!response.ok) {
        throw new Error(await readErrorDetail(response))
    }
    const body = (await response.json()) as { providers?: string[] }
    return body.providers ?? []
}

interface StreamAtlasOptions {
    onEvent: (event: AtlasStreamEvent) => void
    signal?: AbortSignal
}

/**
 * 以 SSE 消费图谱生成接口。
 *
 * 用 fetch 而不是 EventSource：EventSource 只支持 GET、无法携带请求体，
 * 而本接口是 POST + JSON body。代价是要自己解析 SSE 帧格式。
 *
 * 注意状态码的两种含义：
 *  - 开流**之前**的错误（鉴权失败、参数校验、provider 未注册）仍是真实状态码，走 throw；
 *  - 开流**之后**的错误一律是 200 + error 帧，由 onEvent 交付。
 */
export async function streamAtlas(
    query: string,
    provider: string,
    { onEvent, signal }: StreamAtlasOptions,
): Promise<void> {
    const response = await fetch('/api/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, provider }),
        signal,
    })

    if (!response.ok) {
        throw new Error(await readErrorDetail(response))
    }
    if (!response.body) {
        throw new Error('服务端没有返回可读的响应流')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // SSE 以空行分隔帧。最后一段可能是不完整的半帧，留在 buffer 里等下一块。
        const frames = buffer.split('\n\n')
        buffer = frames.pop() ?? ''

        for (const frame of frames) {
            const dataLine = frame
                .split('\n')
                .find((line) => line.startsWith('data: '))
            if (!dataLine) continue

            try {
                onEvent(JSON.parse(dataLine.slice(6)) as AtlasStreamEvent)
            } catch {
                // 单帧坏数据不该打断整条流
            }
        }
    }
}
