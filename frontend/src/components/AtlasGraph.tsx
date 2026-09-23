import Dagre from '@dagrejs/dagre'
import {
    Background,
    Controls,
    MarkerType,
    MiniMap,
    Panel,
    ReactFlow,
    useEdgesState,
    useNodesState,
    type Edge,
    type ReactFlowInstance,
} from '@xyflow/react'
import { useEffect, useMemo, useState } from 'react'
import { CATEGORY_ORDER, CATEGORY_THEME } from '../lib/categoryTheme'
import type { AtlasEdge, AtlasNode } from '../types/atlas'
import { AtlasNodeCard, NODE_HEIGHT, NODE_WIDTH, type AtlasFlowNode } from './AtlasNodeCard'

type AtlasFlowEdge = Edge<{ relation: string }>

const NODE_TYPES = { atlas: AtlasNodeCard }

const EDGE_COLOR = '#94a3b8'

/**
 * 用 dagre 做自动布局。
 *
 * 不自己写分层算法：图谱里存在 `alternative_to`、`influences` 这类关系，
 * 意味着必然有环，手写的 BFS 分层会在环上失效。dagre 会自动破环。
 *
 * dagre 是确定性的：同样的节点与边必定得到同样的坐标。生成过程中每次新增
 * 一个节点都整图重排，已有节点因此基本待在原处，不会有剧烈跳动。
 */
function layout(nodes: AtlasFlowNode[], edges: AtlasFlowEdge[]): AtlasFlowNode[] {
    if (nodes.length === 0) return nodes

    const graph = new Dagre.graphlib.Graph()
    graph.setDefaultEdgeLabel(() => ({}))
    graph.setGraph({ rankdir: 'TB', nodesep: 48, ranksep: 80 })

    for (const node of nodes) {
        graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
    }
    for (const edge of edges) {
        graph.setEdge(edge.source, edge.target)
    }

    Dagre.layout(graph)

    return nodes.map((node) => {
        // dagre 给的是中心点坐标，React Flow 要的是左上角
        const { x, y } = graph.node(node.id)
        return {
            ...node,
            position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
        }
    })
}

function buildGraph(atlasNodes: AtlasNode[], atlasEdges: AtlasEdge[]) {
    const nodes: AtlasFlowNode[] = atlasNodes.map((node) => ({
        id: node.id,
        type: 'atlas',
        position: { x: 0, y: 0 },
        data: node,
    }))

    const edges: AtlasFlowEdge[] = atlasEdges
        // 自环边在布局引擎里没有意义，图上也读不出东西
        .filter((edge) => edge.source !== edge.target)
        .map((edge, index) => ({
            id: `${edge.source}->${edge.target}#${index}`,
            source: edge.source,
            target: edge.target,
            label: edge.relation,
            type: 'smoothstep',
            style: { stroke: EDGE_COLOR, strokeWidth: 1.5 },
            // 箭头不是装饰：每条边的方向都有语义，`depends_on` 与反向关系
            // 含义完全相反，没有箭头这个信息就丢了
            markerEnd: {
                type: MarkerType.ArrowClosed,
                color: EDGE_COLOR,
                width: 18,
                height: 18,
            },
            labelStyle: { fill: '#475569', fontSize: 12, fontWeight: 500 },
            labelBgStyle: { fill: '#ffffff', fillOpacity: 0.95 },
            labelBgPadding: [6, 3] as [number, number],
            labelBgBorderRadius: 4,
        }))

    return { nodes: layout(nodes, edges), edges }
}

interface AtlasGraphProps {
    nodes: AtlasNode[]
    edges: AtlasEdge[]
}

export function AtlasGraph({ nodes: atlasNodes, edges: atlasEdges }: AtlasGraphProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState<AtlasFlowNode>([])
    const [edges, setEdges, onEdgesChange] = useEdgesState<AtlasFlowEdge>([])
    const [instance, setInstance] = useState<ReactFlowInstance<
        AtlasFlowNode,
        AtlasFlowEdge
    > | null>(null)

    // useMemo 的依赖是数组身份，不是内容：父组件每次收到 stage / progress 事件
    // 都会重渲染，但只有节点或边真的增加时这两个数组才是新对象。少了这一层，
    // 每次重渲染都会把用户拖出来的位置抹掉。
    const graph = useMemo(
        () => buildGraph(atlasNodes, atlasEdges),
        [atlasNodes, atlasEdges],
    )

    useEffect(() => {
        setNodes((current) => {
            // 以布局结果为准逐条取值：新节点直接用，老节点则把现有对象"抬"过来，
            // 只覆盖坐标。React Flow 会把实测尺寸（measured）与连接点位置写回
            // 节点对象，若用 buildGraph 造的新对象整体替换，等于宣称"所有节点
            // 尺寸未知"——边的连接点随之失效，整张图会闪一下再重新量一遍。
            // 生成过程中每来一个节点都闪一次，所以必须按 id 合并而不是替换。
            //
            // 顺带也解决了换课题的情况：旧节点不在布局结果里，自然被丢掉。
            const byId = new Map(current.map((node) => [node.id, node]))
            return graph.nodes.map((node) => {
                const existing = byId.get(node.id)
                return existing ? { ...existing, position: node.position } : node
            })
        })

        setEdges(graph.edges)
        // 图在生长，视野得跟着长。否则新节点落在屏幕外，看上去就像卡住了。
        // 重复调用是安全的：新的 fitView 会接管上一次未完成的动画。
        instance?.fitView({ duration: 300, padding: 0.2 })
    }, [graph, instance, setNodes, setEdges])

    const nodeColor = useMemo(
        () => (node: AtlasFlowNode) => CATEGORY_THEME[node.data.category].accent,
        [],
    )

    return (
        <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={setInstance}
            nodeTypes={NODE_TYPES}
            fitView
            minZoom={0.15}
        >
            <Background color="#e2e8f0" gap={20} />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable nodeColor={nodeColor} />

            {/* 左下角被 Controls 占着，右下角是 MiniMap，顶部中间留给进度条 */}
            <Panel position="top-left">
                <div className="flex gap-3 rounded-md border border-slate-200 bg-white/90 px-3 py-1.5 backdrop-blur">
                    {CATEGORY_ORDER.map((category) => (
                        <span
                            key={category}
                            className="flex items-center gap-1.5 text-[11px] text-slate-600"
                        >
                            <span
                                className="h-2 w-2 rounded-full"
                                style={{ backgroundColor: CATEGORY_THEME[category].accent }}
                            />
                            {CATEGORY_THEME[category].label}
                        </span>
                    ))}
                </div>
            </Panel>
        </ReactFlow>
    )
}
