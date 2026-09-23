import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { CATEGORY_THEME } from '../lib/categoryTheme'
import type { AtlasNode } from '../types/atlas'

/** 节点尺寸在布局时需要预先知道，所以固定下来而不是让其自适应内容高度 */
export const NODE_WIDTH = 260
export const NODE_HEIGHT = 108

export type AtlasFlowNode = Node<AtlasNode, 'atlas'>

export function AtlasNodeCard({ data }: NodeProps<AtlasFlowNode>) {
    const theme = CATEGORY_THEME[data.category]

    return (
        <div
            className="flex flex-col gap-1 rounded-lg border border-l-4 px-3 py-2 shadow-sm"
            style={{
                width: NODE_WIDTH,
                height: NODE_HEIGHT,
                borderLeftColor: theme.accent,
                backgroundColor: theme.surface,
            }}
        >
            <Handle type="target" position={Position.Top} className="!invisible" />

            <div className="flex items-baseline justify-between gap-2">
                <span className="truncate text-sm font-semibold text-slate-800">
                    {data.label}
                </span>
                <span
                    className="shrink-0 text-[10px] font-medium"
                    style={{ color: theme.accent }}
                >
                    {theme.label}
                </span>
            </div>

            <p className="line-clamp-3 text-xs leading-snug text-slate-600">
                {data.description}
            </p>

            <Handle type="source" position={Position.Bottom} className="!invisible" />
        </div>
    )
}
