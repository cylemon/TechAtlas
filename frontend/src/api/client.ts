/**
 * 后端所有错误响应体统一是 {"detail": "..."}——HTTP 错误和 SSE 流内的 error 帧
 * 用的是同一个字段名。这里把这层约定收敛到一处，组件只需处理字符串。
 */
export async function readErrorDetail(response: Response): Promise<string> {
    try {
        const body: unknown = await response.json()
        if (
            body !== null &&
            typeof body === 'object' &&
            'detail' in body &&
            typeof body.detail === 'string'
        ) {
            return body.detail
        }
    } catch {
        // 响应体不是 JSON（例如反代返回的 HTML 错误页），回落到状态码
    }
    return `请求失败（HTTP ${response.status}）`
}

/** 把任意抛出物归一成可直接展示的文案 */
export function toMessage(error: unknown): string {
    if (error instanceof Error) return error.message
    return String(error)
}
