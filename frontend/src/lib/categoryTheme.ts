import type { AtlasNodeCategory } from '../types/atlas'

export type Category = AtlasNodeCategory

export interface CategoryTheme {
    /** 图例与节点上显示的中文名 */
    label: string
    /** 强调色：节点左边框、图例圆点 */
    accent: string
    /** 节点底色 */
    surface: string
}

/**
 * category → 视觉的唯一真源。
 *
 * 后端已把 category 收成严格四值枚举，所以这里用 Record<Category, …>：
 * 一旦后端新增分类，TypeScript 会在编译期报缺项，而不是让某个节点渲染成无色。
 */
export const CATEGORY_THEME: Record<Category, CategoryTheme> = {
    core_concept: {
        label: '核心概念',
        accent: '#2563eb',
        surface: '#eff6ff',
    },
    sub_technology: {
        label: '关键子技术',
        accent: '#7c3aed',
        surface: '#f5f3ff',
    },
    tool: {
        label: '工具与生态',
        accent: '#059669',
        surface: '#ecfdf5',
    },
    frontier: {
        label: '前沿发展',
        accent: '#ea580c',
        surface: '#fff7ed',
    },
}

/** 图例顺序，与后端 prompt 里的拆解维度一致 */
export const CATEGORY_ORDER: Category[] = [
    'core_concept',
    'sub_technology',
    'tool',
    'frontier',
]
