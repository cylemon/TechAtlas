// 与 backend/schemas/atlas.py 一一对应
//
// 这里用 type 别名而不是 interface：React Flow 要求节点 data 满足
// Record<string, unknown>，而 TypeScript 只给类型字面量隐式索引签名，
// interface 因为可被声明合并而没有。用 interface 会导致编译报错。

export type AtlasNodeCategory =
    | 'core_concept'
    | 'sub_technology'
    | 'tool'
    | 'frontier'

export type AtlasNode = {
    id: string
    label: string
    category: AtlasNodeCategory
    description: string
    importance: number
}

export type AtlasEdge = {
    source: string
    target: string
    /** 蛇形命名，词表开放：includes / depends_on / enables / alternative_to ... */
    relation: string
}

export type AtlasResponse = {
    topic: string
    summary: string
    nodes: AtlasNode[]
    edges: AtlasEdge[]
    cross_domain_ideas?: string[]
}
