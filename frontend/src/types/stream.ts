import type { AtlasEdge, AtlasNode, AtlasResponse } from './atlas'

/**
 * 后端 SSE 事件协议。
 *
 * 这部分**必须手写**：SSE 对 OpenAPI 是不透明的，接口文档里描述不出来。
 * 与 `atlas.ts` 里那些可以后端生成的类型要分清边界。
 *
 * 四条约定（与 backend/services/atlas.py 的 stream 生成器一致）：
 *  1. 开流之后 HTTP 状态码恒为 200，成败只能看事件；
 *  2. 终止事件是 result 或 error，二选一，不会都出现也不会都不出现；
 *  3. 只有 result / error 是终止事件，其余仅表示进度；
 *  4. 若流关闭却没有收到任何终止事件，说明连接被中途掐断，应视为失败。
 */

export type StageName = 'generating' | 'parsing'

/** TechAtlasResponse 的顶层字段名，代表模型当前正在书写哪一段 */
export type SectionName =
    | 'topic'
    | 'summary'
    | 'nodes'
    | 'edges'
    | 'cross_domain_ideas'

export interface StageEvent {
    type: 'stage'
    stage: StageName
    label: string
}

export interface ProgressEvent {
    type: 'progress'
    section: SectionName | null
    /** 已接收的字符数。后端刻意不给百分比——总量事先不可知 */
    received_chars: number
    elapsed_ms: number
}

export interface ResultEvent {
    type: 'result'
    atlas: AtlasResponse
    elapsed_ms: number
}

export interface ErrorEvent {
    type: 'error'
    detail: string
}

/**
 * 模型每写完一个节点就推送一条，不必等整份 JSON 完成。
 * 后端已逐个走过 Pydantic 校验，到达这里的数据与 result 里的同样可信。
 */
export interface NodeEvent {
    type: 'node'
    node: AtlasNode
}

/**
 * 对应的边事件。后端会把两端节点尚未出现过的边拦下，
 * 所以前端拿到边的两个端点必定已经画在图上。
 */
export interface EdgeEvent {
    type: 'edge'
    edge: AtlasEdge
}

export type AtlasStreamEvent =
    | StageEvent
    | ProgressEvent
    | NodeEvent
    | EdgeEvent
    | ResultEvent
    | ErrorEvent

/** 进度事件里 section 的中文说明，用于展示"正在生成什么" */
export const SECTION_LABEL: Record<SectionName, string> = {
    topic: '课题',
    summary: '概述',
    nodes: '节点',
    edges: '关系',
    cross_domain_ideas: '跨领域思路',
}
